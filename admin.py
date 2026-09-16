import os
import re
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO

import pandas as pd

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    jsonify,
    send_file
)

from flask_login import current_user
from werkzeug.utils import secure_filename

from models import (
    User,
    Category,
    Product,
    Order,
    Courier,
    Shipment,
    ProductImage,
    Review,
    ChatConversation,
    ChatMessage,
    Complaint,
    ComplaintMessage,
    LiveChatRequest
)

from database import db


admin_bp = Blueprint(
    'admin',
    __name__,
    url_prefix='/admin'
)


# ============================================================
# IMAGE UPLOAD CONFIGURATION
# ============================================================

UPLOAD_FOLDER = os.path.join(
    'static',
    'uploads',
    'products'
)

ALLOWED_EXTENSIONS = {
    'png',
    'jpg',
    'jpeg',
    'gif',
    'webp'
}

MAX_IMAGES = 8


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def allowed_file(filename):
    """
    Check whether uploaded file has an allowed extension.
    """

    if not filename:
        return False

    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def checkbox_value(field_name):
    """
    Safely read a checkbox value from Flask request.

    Supports normal HTML checkbox values such as:

        on
        1
        true
        yes
        checked

    Also supports the common pattern:

        <input type="hidden" name="is_active" value="0">
        <input type="checkbox" name="is_active" value="1">

    In that case, if the checkbox is checked, request.form.getlist()
    contains both values and this function correctly returns True.
    """

    values = request.form.getlist(field_name)

    if not values:
        return False

    true_values = {
        'on',
        '1',
        'true',
        'yes',
        'checked'
    }

    return any(
        str(value).strip().lower()
        in true_values
        for value in values
    )


def generate_slug(text):
    """
    Generate a clean URL slug.
    """

    if not text:
        return ''

    text = text.strip().lower()

    text = re.sub(
        r'[^a-z0-9]+',
        '-',
        text
    )

    text = text.strip('-')

    return text


def save_uploaded_file(file):
    """
    Save uploaded image and return URL path.

    Returns:
        str | None
    """

    if not file:
        return None

    if not file.filename:
        return None

    if not allowed_file(file.filename):
        return None

    os.makedirs(
        UPLOAD_FOLDER,
        exist_ok=True
    )

    original_filename = secure_filename(
        file.filename
    )

    if not original_filename:
        return None

    name, extension = os.path.splitext(
        original_filename
    )

    timestamp = datetime.utcnow().strftime(
        '%Y%m%d%H%M%S%f'
    )

    filename = (
        f"{name}_{timestamp}"
        f"{extension.lower()}"
    )

    file_path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    file.save(file_path)

    return '/' + file_path.replace(
        os.sep,
        '/'
    )


def delete_uploaded_file(image_url):
    """
    Delete physical image file from server.
    """

    if not image_url:
        return

    try:

        relative_path = image_url.lstrip('/')

        if relative_path.startswith(
            'static/'
        ):

            file_path = os.path.join(
                os.getcwd(),
                relative_path
            )

            if os.path.isfile(file_path):
                os.remove(file_path)

    except Exception:
        pass


def get_product_images_count(product_id):
    """
    Return current number of product images.
    """

    return ProductImage.query.filter_by(
        product_id=product_id
    ).count()


# ============================================================
# ADMIN REQUIRED DECORATOR
# ============================================================

def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not current_user.is_authenticated:

            flash(
                'Please login to access the admin panel.',
                'warning'
            )

            return redirect(
                url_for(
                    'auth.login',
                    next=request.url
                )
            )

        if current_user.role != 'admin':
            abort(403)

        return f(*args, **kwargs)

    return decorated_function


# ============================================================
# ADMIN ROOT
# ============================================================

@admin_bp.route('/')
def admin_root():

    if (
        current_user.is_authenticated
        and current_user.role == 'admin'
    ):

        return redirect(
            url_for('admin.dashboard')
        )

    return render_template(
        'admin/login.html'
    )


# ============================================================
# DASHBOARD
# ============================================================

@admin_bp.route('/dashboard')
@admin_required
def dashboard():

    total_orders = Order.query.count()

    pending_orders = Order.query.filter_by(
        order_status='Pending'
    ).count()

    confirmed_orders = Order.query.filter_by(
        order_status='Confirmed'
    ).count()

    processing_orders = Order.query.filter_by(
        order_status='Processing'
    ).count()

    shipped_orders = Order.query.filter_by(
        order_status='Shipped'
    ).count()

    out_for_delivery = Order.query.filter_by(
        order_status='Out for Delivery'
    ).count()

    delivered_orders = Order.query.filter_by(
        order_status='Delivered'
    ).count()

    cancelled_orders = Order.query.filter_by(
        order_status='Cancelled'
    ).count()

    returned_orders = Order.query.filter_by(
        order_status='Returned'
    ).count()

    total_customers = User.query.filter_by(
        role='customer'
    ).count()

    total_products = Product.query.count()

    total_sales = (
        db.session.query(
            db.func.sum(
                Order.total_amount
            )
        )
        .filter_by(
            order_status='Delivered'
        )
        .scalar()
        or 0
    )

    # =========================================================
    # COMPLAINT COUNTS
    # =========================================================
    pending_complaints = Complaint.query.filter_by(
        status='Pending'
    ).count()

    in_progress_complaints = Complaint.query.filter_by(
        status='In Progress'
    ).count()

    escalated_complaints = Complaint.query.filter_by(
        is_escalated=True
    ).count()

    resolved_complaints = Complaint.query.filter_by(
        status='Resolved'
    ).count()

    recent_orders = (
        Order.query
        .order_by(
            Order.created_at.desc()
        )
        .limit(10)
        .all()
    )

    monthly_sales = (
        db.session.query(
            db.func.strftime(
                '%Y-%m',
                Order.created_at
            ).label('month'),

            db.func.sum(
                Order.total_amount
            ).label('total')
        )
        .filter_by(
            order_status='Delivered'
        )
        .group_by('month')
        .order_by('month')
        .limit(12)
        .all()
    )

    return render_template(
        'admin/dashboard.html',
        total_orders=total_orders,
        pending_orders=pending_orders,
        confirmed_orders=confirmed_orders,
        processing_orders=processing_orders,
        shipped_orders=shipped_orders,
        out_for_delivery=out_for_delivery,
        delivered_orders=delivered_orders,
        cancelled_orders=cancelled_orders,
        returned_orders=returned_orders,
        total_customers=total_customers,
        total_products=total_products,
        total_sales=total_sales,
        recent_orders=recent_orders,
        monthly_sales=monthly_sales,
        # Complaint counts
        pending_complaints=pending_complaints,
        in_progress_complaints=in_progress_complaints,
        escalated_complaints=escalated_complaints,
        resolved_complaints=resolved_complaints
    )


# ============================================================
# ORDERS
# ============================================================

@admin_bp.route('/orders')
@admin_required
def orders():

    status_filter = request.args.get(
        'status',
        ''
    )

    search_query = request.args.get(
        'q',
        ''
    )

    query = Order.query

    if (
        status_filter
        and status_filter != 'all'
    ):

        query = query.filter_by(
            order_status=status_filter
        )

    if search_query:

        query = query.filter(
            db.or_(
                Order.order_number.contains(
                    search_query
                ),
                Order.customer_name.contains(
                    search_query
                ),
                Order.phone.contains(
                    search_query
                ),
                Order.email.contains(
                    search_query
                )
            )
        )

    orders = (
        query
        .order_by(
            Order.created_at.desc()
        )
        .all()
    )

    statuses = [
        'Pending',
        'Confirmed',
        'Processing',
        'Shipped',
        'Out for Delivery',
        'Delivered',
        'Cancelled',
        'Returned'
    ]

    today = datetime.now().date()

    date_from_today = today.strftime(
        '%Y-%m-%d'
    )

    date_to_today = today.strftime(
        '%Y-%m-%d'
    )

    week_start = today - timedelta(
        days=today.weekday()
    )

    date_from_week = week_start.strftime(
        '%Y-%m-%d'
    )

    date_to_week = today.strftime(
        '%Y-%m-%d'
    )

    month_start = today.replace(
        day=1
    )

    date_from_month = month_start.strftime(
        '%Y-%m-%d'
    )

    date_to_month = today.strftime(
        '%Y-%m-%d'
    )

    return render_template(
        'admin/orders.html',
        orders=orders,
        statuses=statuses,
        current_status=status_filter,
        search_query=search_query,
        date_from_today=date_from_today,
        date_to_today=date_to_today,
        date_from_week=date_from_week,
        date_to_week=date_to_week,
        date_from_month=date_from_month,
        date_to_month=date_to_month
    )


# ============================================================
# EXPORT ORDERS
# ============================================================

@admin_bp.route('/export-orders')
@admin_required
def export_orders():

    status_filter = request.args.get(
        'status',
        ''
    )

    search_query = request.args.get(
        'q',
        ''
    )

    date_from = request.args.get(
        'date_from',
        ''
    )

    date_to = request.args.get(
        'date_to',
        ''
    )

    query = Order.query

    if (
        status_filter
        and status_filter != 'all'
    ):

        query = query.filter_by(
            order_status=status_filter
        )

    if search_query:

        query = query.filter(
            db.or_(
                Order.order_number.contains(
                    search_query
                ),
                Order.customer_name.contains(
                    search_query
                ),
                Order.phone.contains(
                    search_query
                ),
                Order.email.contains(
                    search_query
                )
            )
        )

    if date_from:

        try:

            date_from_obj = datetime.strptime(
                date_from,
                '%Y-%m-%d'
            )

            query = query.filter(
                Order.created_at >= date_from_obj
            )

        except ValueError:
            pass

    if date_to:

        try:

            date_to_obj = datetime.strptime(
                date_to,
                '%Y-%m-%d'
            )

            date_to_obj += timedelta(
                days=1
            )

            query = query.filter(
                Order.created_at < date_to_obj
            )

        except ValueError:
            pass

    orders = (
        query
        .order_by(
            Order.created_at.desc()
        )
        .all()
    )

    data = []

    for order in orders:

        # Group by product name
        product_groups = {}

        for item in order.items:
            product_name = item.product_name
            if product_name in product_groups:
                product_groups[product_name]['quantity'] += item.quantity
                product_groups[product_name]['subtotal'] += item.subtotal
            else:
                product_groups[product_name] = {
                    'quantity': item.quantity,
                    'price': item.price,
                    'subtotal': item.subtotal
                }

        # Create rows for each unique product
        for product_name, details in product_groups.items():
            data.append({
                'Order ID': order.order_number,
                'Order Date': order.created_at.strftime('%Y-%m-%d %H:%M'),
                'Customer Name': order.customer_name,
                'Phone': order.phone,
                'Email': order.email,
                'Address': order.address,
                'City': order.city,
                'Province': order.province,
                'Product Name': product_name,
                'Quantity': details['quantity'],
                'Unit Price': f"Rs. {details['price']:,.0f}",
                'Item Subtotal': f"Rs. {details['subtotal']:,.0f}",
                'Order Subtotal': f"Rs. {order.subtotal:,.0f}",
                'Shipping': f"Rs. {order.shipping_fee:,.0f}",
                'Order Total': f"Rs. {order.total_amount:,.0f}",
                'Payment Method': order.payment_method,
                'Status': order.order_status,
                'Total Products in Order': len(product_groups),
                'Total Quantity in Order': sum(d['quantity'] for d in product_groups.values()),
                'Same Order': 'Yes',
                'Notes': order.notes or ''
            })

    df = pd.DataFrame(data)

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine='openpyxl'
    ) as writer:

        df.to_excel(
            writer,
            sheet_name='Orders',
            index=False
        )

        worksheet = writer.sheets['Orders']

        # =========================================================
        # APPLY FORMATTING - HIGHLIGHT SAME ORDER ROWS
        # =========================================================
        from openpyxl.styles import PatternFill, Border, Side, Font, Alignment

        # Define colors
        order_colors = [
            PatternFill(start_color="E6F3FF", end_color="E6F3FF", fill_type="solid"),  # Light Blue
            PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid"),  # Light Orange
            PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid"),  # Light Green
            PatternFill(start_color="FCE4EC", end_color="FCE4EC", fill_type="solid"),  # Light Pink
            PatternFill(start_color="F3E5F5", end_color="F3E5F5", fill_type="solid"),  # Light Purple
            PatternFill(start_color="E0F7FA", end_color="E0F7FA", fill_type="solid"),  # Light Cyan
            PatternFill(start_color="FFF8E1", end_color="FFF8E1", fill_type="solid"),  # Light Yellow
            PatternFill(start_color="EFEBE9", end_color="EFEBE9", fill_type="solid"),  # Light Brown
        ]

        # Border style
        thin_border = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000')
        )

        # Bold font for Order ID
        bold_font = Font(bold=True)

        # Process rows
        color_index = 0
        current_order_id = None
        start_row = 2  # Excel rows start from 1, header is row 1, data starts from row 2

        for row_idx, row in enumerate(df.iterrows(), start=2):
            order_id = row[1]['Order ID']
            
            # Check if new order group
            if order_id != current_order_id:
                current_order_id = order_id
                # Apply background color to previous group
                if row_idx > start_row:
                    # Apply border to previous group
                    for col in range(1, len(df.columns) + 1):
                        cell = worksheet.cell(row=row_idx - 1, column=col)
                        cell.border = Border(
                            left=Side(style='thin', color='000000'),
                            right=Side(style='thin', color='000000'),
                            top=Side(style='thin', color='000000'),
                            bottom=Side(style='thin', color='000000')
                        )
                
                # Get new color
                color = order_colors[color_index % len(order_colors)]
                color_index += 1

            # Apply background color to current row
            for col in range(1, len(df.columns) + 1):
                cell = worksheet.cell(row=row_idx, column=col)
                cell.fill = color
                cell.border = thin_border
                
                # Bold Order ID
                if col == 1:  # Order ID column
                    cell.font = bold_font

        # Apply border to last group
        if len(df) > 0:
            last_row = len(df) + 1
            for col in range(1, len(df.columns) + 1):
                cell = worksheet.cell(row=last_row, column=col)
                cell.border = Border(
                    left=Side(style='thin', color='000000'),
                    right=Side(style='thin', color='000000'),
                    top=Side(style='thin', color='000000'),
                    bottom=Side(style='thin', color='000000')
                )

        # Auto-adjust column widths
        for column in worksheet.columns:

            max_length = 0

            column_letter = (
                column[0].column_letter
            )

            for cell in column:

                try:

                    if len(
                        str(cell.value)
                    ) > max_length:

                        max_length = len(
                            str(cell.value)
                        )

                except Exception:
                    pass

            worksheet.column_dimensions[
                column_letter
            ].width = min(
                max_length + 2,
                60
            )

    output.seek(0)

    filename = (
        f"orders_export_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        f".xlsx"
    )

    return send_file(
        output,
        mimetype=(
            'application/vnd.openxmlformats-'
            'officedocument.spreadsheetml.sheet'
        ),
        as_attachment=True,
        download_name=filename
    )


# ============================================================
# ORDER DETAIL
# ============================================================

@admin_bp.route(
    '/order/<int:order_id>'
)
@admin_required
def order_detail(order_id):

    order = Order.query.get_or_404(
        order_id
    )

    couriers = Courier.query.filter_by(
        is_active=True
    ).all()

    return render_template(
        'admin/order_detail.html',
        order=order,
        couriers=couriers
    )


# ============================================================
# UPDATE ORDER STATUS
# ============================================================

@admin_bp.route(
    '/order/<int:order_id>/update-status',
    methods=['POST']
)
@admin_required
def update_order_status(order_id):

    order = Order.query.get_or_404(
        order_id
    )

    status = request.form.get(
        'status'
    )

    valid_statuses = [
        'Pending',
        'Confirmed',
        'Processing',
        'Shipped',
        'Out for Delivery',
        'Delivered',
        'Cancelled',
        'Returned'
    ]

    if status in valid_statuses:

        order.order_status = status
        order.updated_at = datetime.utcnow()

        db.session.commit()

        flash(
            f'Order status updated to {status}.',
            'success'
        )

    else:

        flash(
            'Invalid status.',
            'danger'
        )

    return redirect(
        url_for(
            'admin.order_detail',
            order_id=order_id
        )
    )


# ============================================================
# MARK ORDER AS DELIVERED
# ============================================================

@admin_bp.route(
    '/order/<int:order_id>/mark-delivered',
    methods=['POST']
)
@admin_required
def mark_order_delivered(order_id):

    order = Order.query.get_or_404(order_id)

    # Check if already delivered
    if order.order_status == 'Delivered':
        flash(
            f'Order {order.order_number} is already marked as Delivered.',
            'warning'
        )
        return redirect(url_for('admin.orders'))

    try:
        # Update status to Delivered
        order.order_status = 'Delivered'
        order.updated_at = datetime.utcnow()

        # Add delivery notes if provided
        notes = request.form.get('notes', '').strip()
        if notes:
            if order.notes:
                order.notes = order.notes + f'\n\nDelivery notes ({datetime.now().strftime('%Y-%m-%d %H:%M')}): {notes}'
            else:
                order.notes = f'Delivery notes ({datetime.now().strftime('%Y-%m-%d %H:%M')}): {notes}'

        db.session.commit()

        flash(
            f'Order {order.order_number} marked as Delivered! Customer can now review products.',
            'success'
        )

    except Exception as e:
        db.session.rollback()
        flash(
            f'Error marking order as delivered: {str(e)}',
            'danger'
        )

    return redirect(url_for('admin.orders'))


# ============================================================
# UPDATE SHIPMENT
# ============================================================

@admin_bp.route(
    '/order/<int:order_id>/update-shipment',
    methods=['POST']
)
@admin_required
def update_shipment(order_id):

    order = Order.query.get_or_404(
        order_id
    )

    courier_id = request.form.get(
        'courier_id'
    )

    tracking_number = request.form.get(
        'tracking_number',
        ''
    ).strip()

    tracking_url = request.form.get(
        'tracking_url',
        ''
    ).strip()

    shipment_date = request.form.get(
        'shipment_date'
    )

    shipping_status = request.form.get(
        'shipping_status'
    )

    admin_notes = request.form.get(
        'admin_notes',
        ''
    ).strip()

    shipment = Shipment.query.filter_by(
        order_id=order_id
    ).first()

    if not shipment:

        shipment = Shipment(
            order_id=order_id
        )

    try:

        if courier_id:

            shipment.courier_id = int(
                courier_id
            )

        else:

            shipment.courier_id = None

        shipment.tracking_number = (
            tracking_number or None
        )

        shipment.tracking_url = (
            tracking_url or None
        )

        if shipment_date:

            shipment.shipment_date = (
                datetime.strptime(
                    shipment_date,
                    '%Y-%m-%d'
                )
            )

        else:

            shipment.shipment_date = None

        shipment.shipping_status = (
            shipping_status or None
        )

        shipment.admin_notes = (
            admin_notes or None
        )

        shipment.updated_at = (
            datetime.utcnow()
        )

        db.session.add(shipment)

        if (
            shipping_status == 'In Transit'
            and order.order_status == 'Processing'
        ):

            order.order_status = 'Shipped'
            order.updated_at = datetime.utcnow()

        db.session.commit()

        flash(
            'Shipment details updated successfully!',
            'success'
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f'Error updating shipment: {str(e)}',
            'danger'
        )

    return redirect(
        url_for(
            'admin.order_detail',
            order_id=order_id
        )
    )


# ============================================================
# DELETE SHIPMENT
# ============================================================

@admin_bp.route(
    '/order/<int:order_id>/delete-shipment',
    methods=['POST']
)
@admin_required
def delete_shipment(order_id):

    shipment = Shipment.query.filter_by(
        order_id=order_id
    ).first()

    if not shipment:

        return jsonify({
            'success': False,
            'message': 'Shipment not found.'
        })

    try:

        db.session.delete(shipment)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Shipment deleted successfully!'
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            'success': False,
            'message': str(e)
        })


# ============================================================
# PRODUCTS
# ============================================================

@admin_bp.route('/products')
@admin_required
def products():

    products = (
        Product.query
        .order_by(
            Product.created_at.desc()
        )
        .all()
    )

    return render_template(
        'admin/products.html',
        products=products
    )


# ============================================================
# ADD PRODUCT
# ============================================================

@admin_bp.route(
    '/add-product',
    methods=['GET', 'POST']
)
@admin_required
def add_product():

    categories = Category.query.filter_by(
        is_active=True
    ).all()

    if request.method == 'POST':

        try:

            # ------------------------------------------------
            # BASIC DATA
            # ------------------------------------------------

            name = request.form.get(
                'name',
                ''
            ).strip()

            slug = request.form.get(
                'slug',
                ''
            ).strip()

            short_description = request.form.get(
                'short_description',
                ''
            ).strip()

            description = request.form.get(
                'description',
                ''
            ).strip()

            # ------------------------------------------------
            # PRICE
            # ------------------------------------------------

            price_raw = request.form.get(
                'price',
                '0'
            ).strip()

            sale_price_raw = request.form.get(
                'sale_price',
                ''
            ).strip()

            try:

                price = float(
                    price_raw
                )

            except ValueError:

                flash(
                    'Invalid product price.',
                    'danger'
                )

                return render_template(
                    'admin/add_product.html',
                    categories=categories
                )

            try:

                sale_price = (
                    float(sale_price_raw)
                    if sale_price_raw
                    else None
                )

            except ValueError:

                flash(
                    'Invalid sale price.',
                    'danger'
                )

                return render_template(
                    'admin/add_product.html',
                    categories=categories
                )

            # =================================================
            # AUTO-CALCULATE DISCOUNT PERCENTAGE
            # =================================================
            discount_percentage = 0
            if sale_price and sale_price < price and price > 0:
                discount_percentage = round(((price - sale_price) / price) * 100)

            # ------------------------------------------------
            # OTHER DATA
            # ------------------------------------------------

            category_id = request.form.get(
                'category_id'
            )

            brand = request.form.get(
                'brand',
                ''
            ).strip()

            stock_raw = request.form.get(
                'stock_quantity',
                '0'
            ).strip()

            try:

                stock_quantity = int(
                    stock_raw
                )

            except ValueError:

                flash(
                    'Invalid stock quantity.',
                    'danger'
                )

                return render_template(
                    'admin/add_product.html',
                    categories=categories
                )

            sku = request.form.get(
                'sku',
                ''
            ).strip()

            # =================================================
            # ROBUST CHECKBOX HANDLING
            # =================================================

            is_featured = checkbox_value(
                'is_featured'
            )

            is_bestseller = checkbox_value(
                'is_bestseller'
            )

            is_new = checkbox_value(
                'is_new'
            )

            is_active = checkbox_value(
                'is_active'
            )

            # ------------------------------------------------
            # VALIDATION
            # ------------------------------------------------

            if not name:

                flash(
                    'Product name is required.',
                    'danger'
                )

                return render_template(
                    'admin/add_product.html',
                    categories=categories
                )

            if not slug:

                slug = generate_slug(
                    name
                )

            else:

                slug = generate_slug(
                    slug
                )

            if not slug:

                flash(
                    'Unable to generate product slug.',
                    'danger'
                )

                return render_template(
                    'admin/add_product.html',
                    categories=categories
                )

            existing_slug = Product.query.filter_by(
                slug=slug
            ).first()

            if existing_slug:

                flash(
                    'Slug already exists. Please use a different slug.',
                    'danger'
                )

                return render_template(
                    'admin/add_product.html',
                    categories=categories
                )

            if price <= 0:

                flash(
                    'Price must be greater than 0.',
                    'danger'
                )

                return render_template(
                    'admin/add_product.html',
                    categories=categories
                )

            if sale_price is not None:

                if sale_price < 0:

                    flash(
                        'Sale price cannot be negative.',
                        'danger'
                    )

                    return render_template(
                        'admin/add_product.html',
                        categories=categories
                    )

                if sale_price > price:

                    flash(
                        'Sale price cannot be greater than regular price.',
                        'danger'
                    )

                    return render_template(
                        'admin/add_product.html',
                        categories=categories
                    )

            if stock_quantity < 0:

                flash(
                    'Stock quantity cannot be negative.',
                    'danger'
                )

                return render_template(
                    'admin/add_product.html',
                    categories=categories
                )

            # ------------------------------------------------
            # SKU DUPLICATE CHECK
            # ------------------------------------------------

            if sku:

                existing_sku = Product.query.filter_by(
                    sku=sku
                ).first()

                if existing_sku:

                    flash(
                        'SKU already exists.',
                        'danger'
                    )

                    return render_template(
                        'admin/add_product.html',
                        categories=categories
                    )

            # ------------------------------------------------
            # CREATE PRODUCT
            # ------------------------------------------------

            product = Product(
                name=name,
                slug=slug,
                short_description=short_description,
                description=description,
                price=price,
                sale_price=sale_price,
                discount_percentage=discount_percentage,  # Auto-calculated
                category_id=(
                    int(category_id)
                    if category_id
                    else None
                ),
                brand=brand or None,
                stock_quantity=stock_quantity,
                sku=sku or None,

                # Checkbox values
                is_featured=is_featured,
                is_bestseller=is_bestseller,
                is_new=is_new,
                is_active=is_active
            )

            db.session.add(product)

            db.session.flush()

            # ------------------------------------------------
            # IMAGES
            # ------------------------------------------------

            files = request.files.getlist(
                'images'
            )

            valid_files = [
                file
                for file in files
                if file
                and file.filename
                and allowed_file(file.filename)
            ]

            if len(valid_files) > MAX_IMAGES:

                valid_files = valid_files[
                    :MAX_IMAGES
                ]

                flash(
                    'Maximum 8 images allowed. '
                    'Only the first 8 images were uploaded.',
                    'warning'
                )

            uploaded_count = 0

            for index, file in enumerate(
                valid_files
            ):

                uploaded_path = save_uploaded_file(
                    file
                )

                if not uploaded_path:
                    continue

                product_image = ProductImage(
                    product_id=product.id,
                    image_url=uploaded_path,
                    is_main=(
                        index == 0
                    ),
                    display_order=index
                )

                db.session.add(
                    product_image
                )

                if index == 0:

                    product.main_image = (
                        uploaded_path
                    )

                uploaded_count += 1

            db.session.commit()

            flash_msg = f'Product added successfully! {uploaded_count} image(s) uploaded.'
            if discount_percentage > 0:
                flash_msg += f' Discount: {discount_percentage}%'

            flash(flash_msg, 'success')

            return redirect(
                url_for(
                    'admin.products'
                )
            )

        except Exception as e:

            db.session.rollback()

            flash(
                f'Error adding product: {str(e)}',
                'danger'
            )

    return render_template(
        'admin/add_product.html',
        categories=categories
    )


# ============================================================
# EDIT PRODUCT
# ============================================================

@admin_bp.route(
    '/edit-product/<int:product_id>',
    methods=['GET', 'POST']
)
@admin_required
def edit_product(product_id):

    product = Product.query.get_or_404(
        product_id
    )

    categories = Category.query.filter_by(
        is_active=True
    ).all()

    if request.method == 'POST':

        try:

            # =================================================
            # GET FORM DATA
            # =================================================

            name = request.form.get(
                'name',
                ''
            ).strip()

            slug = request.form.get(
                'slug',
                ''
            ).strip()

            short_description = request.form.get(
                'short_description',
                ''
            ).strip()

            description = request.form.get(
                'description',
                ''
            ).strip()

            price_raw = request.form.get(
                'price',
                '0'
            ).strip()

            sale_price_raw = request.form.get(
                'sale_price',
                ''
            ).strip()

            category_id = request.form.get(
                'category_id'
            )

            brand = request.form.get(
                'brand',
                ''
            ).strip()

            stock_raw = request.form.get(
                'stock_quantity',
                '0'
            ).strip()

            sku = request.form.get(
                'sku',
                ''
            ).strip()

            # =================================================
            # ROBUST CHECKBOX HANDLING
            # =================================================

            is_featured = checkbox_value(
                'is_featured'
            )

            is_bestseller = checkbox_value(
                'is_bestseller'
            )

            is_new = checkbox_value(
                'is_new'
            )

            is_active = checkbox_value(
                'is_active'
            )

            # =================================================
            # VALIDATE NAME
            # =================================================

            if not name:

                flash(
                    'Product name is required.',
                    'danger'
                )

                return render_template(
                    'admin/edit_product.html',
                    product=product,
                    categories=categories
                )

            # =================================================
            # SLUG
            # =================================================

            if not slug:

                slug = generate_slug(
                    name
                )

            else:

                slug = generate_slug(
                    slug
                )

            if not slug:

                flash(
                    'Product slug is required.',
                    'danger'
                )

                return render_template(
                    'admin/edit_product.html',
                    product=product,
                    categories=categories
                )

            # =================================================
            # CHECK DUPLICATE SLUG
            # =================================================

            existing_slug = (
                Product.query
                .filter(
                    Product.slug == slug,
                    Product.id != product.id
                )
                .first()
            )

            if existing_slug:

                flash(
                    'Slug already exists. '
                    'Please use a different slug.',
                    'danger'
                )

                return render_template(
                    'admin/edit_product.html',
                    product=product,
                    categories=categories
                )

            # =================================================
            # PRICE
            # =================================================

            try:

                price = float(
                    price_raw
                )

            except ValueError:

                flash(
                    'Invalid product price.',
                    'danger'
                )

                return render_template(
                    'admin/edit_product.html',
                    product=product,
                    categories=categories
                )

            if price <= 0:

                flash(
                    'Price must be greater than 0.',
                    'danger'
                )

                return render_template(
                    'admin/edit_product.html',
                    product=product,
                    categories=categories
                )

            # =================================================
            # SALE PRICE
            # =================================================

            try:

                sale_price = (
                    float(sale_price_raw)
                    if sale_price_raw
                    else None
                )

            except ValueError:

                flash(
                    'Invalid sale price.',
                    'danger'
                )

                return render_template(
                    'admin/edit_product.html',
                    product=product,
                    categories=categories
                )

            if sale_price is not None:

                if sale_price < 0:

                    flash(
                        'Sale price cannot be negative.',
                        'danger'
                    )

                    return render_template(
                        'admin/edit_product.html',
                        product=product,
                        categories=categories
                    )

                if sale_price > price:

                    flash(
                        'Sale price cannot be greater than regular price.',
                        'danger'
                    )

                    return render_template(
                        'admin/edit_product.html',
                        product=product,
                        categories=categories
                    )

            # =================================================
            # AUTO-CALCULATE DISCOUNT PERCENTAGE
            # =================================================
            discount_percentage = product.discount_percentage or 0
            if sale_price and sale_price < price and price > 0:
                discount_percentage = round(((price - sale_price) / price) * 100)
            elif not sale_price:
                discount_percentage = 0

            # =================================================
            # STOCK
            # =================================================

            try:

                stock_quantity = int(
                    stock_raw
                )

            except ValueError:

                flash(
                    'Invalid stock quantity.',
                    'danger'
                )

                return render_template(
                    'admin/edit_product.html',
                    product=product,
                    categories=categories
                )

            if stock_quantity < 0:

                flash(
                    'Stock quantity cannot be negative.',
                    'danger'
                )

                return render_template(
                    'admin/edit_product.html',
                    product=product,
                    categories=categories
                )

            # =================================================
            # SKU DUPLICATE CHECK
            # =================================================

            if sku:

                existing_sku = (
                    Product.query
                    .filter(
                        Product.sku == sku,
                        Product.id != product.id
                    )
                    .first()
                )

                if existing_sku:

                    flash(
                        'SKU already exists.',
                        'danger'
                    )

                    return render_template(
                        'admin/edit_product.html',
                        product=product,
                        categories=categories
                    )

            # =================================================
            # UPDATE PRODUCT FIELDS
            # =================================================

            product.name = name

            product.slug = slug

            product.short_description = (
                short_description
                or None
            )

            product.description = (
                description
                or None
            )

            product.price = price

            product.sale_price = sale_price

            product.discount_percentage = discount_percentage  # Auto-calculated

            product.category_id = (
                int(category_id)
                if category_id
                else None
            )

            product.brand = (
                brand
                or None
            )

            product.stock_quantity = (
                stock_quantity
            )

            product.sku = (
                sku
                or None
            )

            # =================================================
            # SAVE CHECKBOX STATES
            # =================================================

            product.is_featured = (
                is_featured
            )

            product.is_bestseller = (
                is_bestseller
            )

            product.is_new = (
                is_new
            )

            product.is_active = (
                is_active
            )

            if hasattr(
                product,
                'updated_at'
            ):

                product.updated_at = (
                    datetime.utcnow()
                )

            # =================================================
            # HANDLE NEW IMAGES
            # =================================================

            existing_images = (
                ProductImage.query
                .filter_by(
                    product_id=product.id
                )
                .order_by(
                    ProductImage.display_order.asc()
                )
                .all()
            )

            existing_count = len(
                existing_images
            )

            remaining_slots = (
                MAX_IMAGES - existing_count
            )

            files = request.files.getlist(
                'images'
            )

            valid_files = [
                file
                for file in files
                if file
                and file.filename
                and allowed_file(file.filename)
            ]

            if remaining_slots <= 0:

                if valid_files:

                    flash(
                        'Maximum 8 images already exist. '
                        'No new images were added.',
                        'warning'
                    )

            else:

                if len(valid_files) > remaining_slots:

                    valid_files = valid_files[
                        :remaining_slots
                    ]

                    flash(
                        f'Only {remaining_slots} '
                        f'new image(s) can be added. '
                        f'Maximum {MAX_IMAGES} images total.',
                        'warning'
                    )

                if existing_images:

                    max_display_order = max(
                        [
                            image.display_order or 0
                            for image in existing_images
                        ]
                    )

                else:

                    max_display_order = -1

                has_main_image = any(
                    image.is_main
                    for image in existing_images
                )

                for index, file in enumerate(
                    valid_files
                ):

                    uploaded_path = (
                        save_uploaded_file(
                            file
                        )
                    )

                    if not uploaded_path:
                        continue

                    new_display_order = (
                        max_display_order
                        + index
                        + 1
                    )

                    make_main = (
                        not has_main_image
                        and index == 0
                    )

                    product_image = ProductImage(
                        product_id=product.id,
                        image_url=uploaded_path,
                        is_main=make_main,
                        display_order=new_display_order
                    )

                    db.session.add(
                        product_image
                    )

                    if make_main:

                        for old_image in (
                            existing_images
                        ):

                            old_image.is_main = False

                        product.main_image = (
                            uploaded_path
                        )

                        has_main_image = True

            # =================================================
            # FIX MAIN IMAGE
            # =================================================

            current_main_image = (
                ProductImage.query
                .filter_by(
                    product_id=product.id,
                    is_main=True
                )
                .order_by(
                    ProductImage.display_order.asc()
                )
                .first()
            )

            if current_main_image:

                product.main_image = (
                    current_main_image.image_url
                )

            elif (
                not existing_images
                and not valid_files
            ):

                product.main_image = None

            # =================================================
            # SAVE
            # =================================================

            db.session.commit()

            flash_msg = 'Product updated successfully!'
            if discount_percentage > 0:
                flash_msg += f' Discount: {discount_percentage}%'

            flash(flash_msg, 'success')

            return redirect(
                url_for(
                    'admin.products'
                )
            )

        except Exception as e:

            db.session.rollback()

            flash(
                f'Error updating product: {str(e)}',
                'danger'
            )

    return render_template(
        'admin/edit_product.html',
        product=product,
        categories=categories
    )


# ============================================================
# DELETE PRODUCT IMAGE
# ============================================================

@admin_bp.route(
    '/delete-product-image/<int:image_id>',
    methods=['POST']
)
@admin_required
def delete_product_image(image_id):

    image = ProductImage.query.get_or_404(
        image_id
    )

    product_id = image.product_id

    product = Product.query.get_or_404(
        product_id
    )

    try:

        was_main = image.is_main

        image_url = image.image_url

        db.session.delete(image)

        if was_main:

            next_image = (
                ProductImage.query
                .filter(
                    ProductImage.product_id == product_id,
                    ProductImage.id != image_id
                )
                .order_by(
                    ProductImage.display_order.asc()
                )
                .first()
            )

            if next_image:

                ProductImage.query.filter_by(
                    product_id=product_id
                ).update({
                    'is_main': False
                })

                next_image.is_main = True

                product.main_image = (
                    next_image.image_url
                )

            else:

                product.main_image = None

        if hasattr(
            product,
            'updated_at'
        ):

            product.updated_at = (
                datetime.utcnow()
            )

        db.session.commit()

        delete_uploaded_file(
            image_url
        )

        flash(
            'Image deleted successfully!',
            'success'
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f'Error deleting image: {str(e)}',
            'danger'
        )

    return redirect(
        url_for(
            'admin.edit_product',
            product_id=product_id
        )
    )


# ============================================================
# SET MAIN PRODUCT IMAGE
# ============================================================

@admin_bp.route(
    '/set-main-image/<int:image_id>',
    methods=['POST']
)
@admin_required
def set_main_image(image_id):

    image = ProductImage.query.get_or_404(
        image_id
    )

    product_id = image.product_id

    product = Product.query.get_or_404(
        product_id
    )

    try:

        ProductImage.query.filter_by(
            product_id=product_id
        ).update({
            'is_main': False
        })

        image.is_main = True

        product.main_image = (
            image.image_url
        )

        if hasattr(
            product,
            'updated_at'
        ):

            product.updated_at = (
                datetime.utcnow()
            )

        db.session.commit()

        flash(
            'Main image updated successfully!',
            'success'
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f'Error updating main image: {str(e)}',
            'danger'
        )

    return redirect(
        url_for(
            'admin.edit_product',
            product_id=product_id
        )
    )


# ============================================================
# DELETE PRODUCT
# ============================================================

@admin_bp.route(
    '/delete-product/<int:product_id>',
    methods=['POST']
)
@admin_required
def delete_product(product_id):

    product = Product.query.get_or_404(
        product_id
    )

    if product.order_items:

        flash(
            'Cannot delete this product because it has '
            'been ordered by customers. You can deactivate '
            'it instead.',
            'danger'
        )

        return redirect(
            url_for('admin.products')
        )

    if product.wishlist_items:

        flash(
            'Cannot delete this product because it is in '
            'some customers\' wishlists. You can deactivate '
            'it instead.',
            'danger'
        )

        return redirect(
            url_for('admin.products')
        )

    try:

        images = ProductImage.query.filter_by(
            product_id=product_id
        ).all()

        image_urls = [
            image.image_url
            for image in images
        ]

        ProductImage.query.filter_by(
            product_id=product_id
        ).delete()

        db.session.delete(
            product
        )

        db.session.commit()

        for image_url in image_urls:

            delete_uploaded_file(
                image_url
            )

        flash(
            'Product deleted successfully!',
            'success'
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f'Error deleting product: {str(e)}',
            'danger'
        )

    return redirect(
        url_for('admin.products')
    )


# ============================================================
# DEACTIVATE PRODUCT
# ============================================================

@admin_bp.route(
    '/deactivate-product/<int:product_id>',
    methods=['POST']
)
@admin_required
def deactivate_product(product_id):

    product = Product.query.get_or_404(
        product_id
    )

    try:

        product.is_active = False

        if hasattr(
            product,
            'updated_at'
        ):

            product.updated_at = (
                datetime.utcnow()
            )

        db.session.commit()

        flash(
            'Product has been deactivated.',
            'success'
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f'Error deactivating product: {str(e)}',
            'danger'
        )

    return redirect(
        url_for('admin.products')
    )


# ============================================================
# CATEGORIES
# ============================================================

@admin_bp.route('/categories')
@admin_required
def categories():

    categories = (
        Category.query
        .order_by(
            Category.name
        )
        .all()
    )

    return render_template(
        'admin/categories.html',
        categories=categories
    )


# ============================================================
# ADD CATEGORY
# ============================================================

@admin_bp.route(
    '/add-category',
    methods=['POST']
)
@admin_required
def add_category():

    name = request.form.get(
        'name',
        ''
    ).strip()

    description = request.form.get(
        'description',
        ''
    ).strip()

    if not name:

        flash(
            'Category name is required.',
            'danger'
        )

        return redirect(
            url_for('admin.categories')
        )

    slug = generate_slug(
        name
    )

    if Category.query.filter_by(
        slug=slug
    ).first():

        flash(
            'Category already exists.',
            'danger'
        )

        return redirect(
            url_for('admin.categories')
        )

    try:

        category = Category(
            name=name,
            slug=slug,
            description=description
        )

        db.session.add(category)

        db.session.commit()

        flash(
            'Category added successfully!',
            'success'
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f'Error adding category: {str(e)}',
            'danger'
        )

    return redirect(
        url_for('admin.categories')
    )


# ============================================================
# EDIT CATEGORY
# ============================================================

@admin_bp.route(
    '/edit-category/<int:category_id>',
    methods=['POST']
)
@admin_required
def edit_category(category_id):

    category = Category.query.get_or_404(
        category_id
    )

    name = request.form.get(
        'name',
        ''
    ).strip()

    description = request.form.get(
        'description',
        ''
    ).strip()

    is_active = checkbox_value(
        'is_active'
    )

    if not name:

        flash(
            'Category name is required.',
            'danger'
        )

        return redirect(
            url_for('admin.categories')
        )

    try:

        category.name = name

        category.slug = generate_slug(
            name
        )

        category.description = (
            description
        )

        category.is_active = (
            is_active
        )

        if hasattr(
            category,
            'updated_at'
        ):

            category.updated_at = (
                datetime.utcnow()
            )

        db.session.commit()

        flash(
            'Category updated successfully!',
            'success'
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f'Error updating category: {str(e)}',
            'danger'
        )

    return redirect(
        url_for('admin.categories')
    )


# ============================================================
# DELETE CATEGORY
# ============================================================

@admin_bp.route(
    '/delete-category/<int:category_id>',
    methods=['POST']
)
@admin_required
def delete_category(category_id):

    category = Category.query.get_or_404(
        category_id
    )

    if category.products:

        flash(
            'Cannot delete category with products. '
            'Remove products first.',
            'danger'
        )

        return redirect(
            url_for('admin.categories')
        )

    try:

        db.session.delete(
            category
        )

        db.session.commit()

        flash(
            'Category deleted successfully!',
            'success'
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f'Error deleting category: {str(e)}',
            'danger'
        )

    return redirect(
        url_for('admin.categories')
    )


# ============================================================
# CUSTOMERS
# ============================================================

@admin_bp.route('/customers')
@admin_required
def customers():

    customers = (
        User.query
        .filter_by(
            role='customer'
        )
        .order_by(
            User.created_at.desc()
        )
        .all()
    )

    return render_template(
        'admin/customers.html',
        customers=customers
    )


# ============================================================
# TOGGLE CUSTOMER STATUS
# ============================================================

@admin_bp.route(
    '/customer/<int:user_id>/toggle-status',
    methods=['POST']
)
@admin_required
def toggle_customer_status(user_id):

    user = User.query.get_or_404(
        user_id
    )

    if user.role == 'admin':

        flash(
            'Cannot deactivate admin user.',
            'danger'
        )

        return redirect(
            url_for('admin.customers')
        )

    user.is_active = not user.is_active

    if hasattr(
        user,
        'updated_at'
    ):

        user.updated_at = (
            datetime.utcnow()
        )

    db.session.commit()

    status = (
        'activated'
        if user.is_active
        else 'deactivated'
    )

    flash(
        f'Customer {status} successfully!',
        'success'
    )

    return redirect(
        url_for('admin.customers')
    )


# ============================================================
# SHIPMENTS
# ============================================================

@admin_bp.route('/shipments')
@admin_required
def shipments():

    shipments = (
        Shipment.query
        .order_by(
            Shipment.created_at.desc()
        )
        .all()
    )

    couriers = Courier.query.filter_by(
        is_active=True
    ).all()

    return render_template(
        'admin/shipments.html',
        shipments=shipments,
        couriers=couriers
    )


# ============================================================
# ADD COURIER
# ============================================================

@admin_bp.route(
    '/add-courier',
    methods=['POST']
)
@admin_required
def add_courier():

    name = request.form.get(
        'name',
        ''
    ).strip()

    website = request.form.get(
        'website',
        ''
    ).strip()

    tracking_url_template = request.form.get(
        'tracking_url_template',
        ''
    ).strip()

    if not name:

        flash(
            'Courier name is required.',
            'danger'
        )

        return redirect(
            url_for('admin.shipments')
        )

    try:

        courier = Courier(
            name=name,
            website=website or None,
            tracking_url_template=(
                tracking_url_template
                or None
            )
        )

        db.session.add(courier)

        db.session.commit()

        flash(
            'Courier added successfully!',
            'success'
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f'Error adding courier: {str(e)}',
            'danger'
        )

    return redirect(
        url_for('admin.shipments')
    )


# ============================================================
# EDIT COURIER
# ============================================================

@admin_bp.route(
    '/edit-courier/<int:courier_id>',
    methods=['GET', 'POST']
)
@admin_required
def edit_courier(courier_id):

    courier = Courier.query.get_or_404(
        courier_id
    )

    if request.method == 'POST':

        name = request.form.get(
            'name',
            ''
        ).strip()

        website = request.form.get(
            'website',
            ''
        ).strip()

        tracking_url_template = request.form.get(
            'tracking_url_template',
            ''
        ).strip()

        is_active = checkbox_value(
            'is_active'
        )

        if not name:

            flash(
                'Courier name is required.',
                'danger'
            )

            return redirect(
                url_for('admin.shipments')
            )

        try:

            courier.name = name

            courier.website = (
                website or None
            )

            courier.tracking_url_template = (
                tracking_url_template
                or None
            )

            courier.is_active = (
                is_active
            )

            if hasattr(
                courier,
                'updated_at'
            ):

                courier.updated_at = (
                    datetime.utcnow()
                )

            db.session.commit()

            flash(
                'Courier updated successfully!',
                'success'
            )

        except Exception as e:

            db.session.rollback()

            flash(
                f'Error updating courier: {str(e)}',
                'danger'
            )

        return redirect(
            url_for('admin.shipments')
        )

    return render_template(
        'admin/edit_courier.html',
        courier=courier
    )


# ============================================================
# DELETE COURIER
# ============================================================

@admin_bp.route(
    '/delete-courier/<int:courier_id>',
    methods=['POST']
)
@admin_required
def delete_courier(courier_id):

    courier = Courier.query.get_or_404(
        courier_id
    )

    shipment = Shipment.query.filter_by(
        courier_id=courier_id
    ).first()

    if shipment:

        return jsonify({
            'success': False,
            'message': (
                'Cannot delete courier. '
                'It is being used by existing shipments.'
            )
        })

    try:

        db.session.delete(
            courier
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Courier deleted successfully!'
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            'success': False,
            'message': str(e)
        })


# ============================================================
# GET COURIER API
# ============================================================

@admin_bp.route(
    '/api/courier/<int:courier_id>'
)
@admin_required
def get_courier(courier_id):

    courier = Courier.query.get_or_404(
        courier_id
    )

    return jsonify({
        'success': True,
        'courier': {
            'id': courier.id,
            'name': courier.name,
            'website': courier.website,
            'tracking_url_template': (
                courier.tracking_url_template
            ),
            'is_active': courier.is_active
        }
    })


# ============================================================
# REVIEWS
# ============================================================

@admin_bp.route('/reviews')
@admin_required
def reviews():

    filter_type = request.args.get(
        'filter',
        'all'
    )

    query = Review.query

    if filter_type == 'pending':

        query = query.filter_by(
            is_approved=False
        )

    elif filter_type == 'approved':

        query = query.filter_by(
            is_approved=True
        )

    reviews = (
        query
        .order_by(
            Review.created_at.desc()
        )
        .all()
    )

    total_reviews = Review.query.count()

    pending_reviews = (
        Review.query
        .filter_by(
            is_approved=False
        )
        .count()
    )

    approved_reviews = (
        Review.query
        .filter_by(
            is_approved=True
        )
        .count()
    )

    rejected_reviews = 0

    return render_template(
        'admin/reviews.html',
        reviews=reviews,
        filter_type=filter_type,
        total_reviews=total_reviews,
        pending_reviews=pending_reviews,
        approved_reviews=approved_reviews,
        rejected_reviews=rejected_reviews
    )


# ============================================================
# APPROVE REVIEW
# ============================================================

@admin_bp.route(
    '/review/<int:review_id>/approve',
    methods=['POST']
)
@admin_required
def approve_review(review_id):

    review = Review.query.get_or_404(
        review_id
    )

    try:

        review.is_approved = True

        if hasattr(
            review,
            'updated_at'
        ):

            review.updated_at = (
                datetime.utcnow()
            )

        product = review.product

        approved_reviews = (
            Review.query
            .filter_by(
                product_id=product.id,
                is_approved=True
            )
            .all()
        )

        approved_reviews = [
            r for r in approved_reviews
            if r.id != review.id
        ]

        approved_reviews.append(
            review
        )

        if approved_reviews:

            total_rating = sum(
                r.rating
                for r in approved_reviews
            )

            product.rating = round(
                total_rating /
                len(approved_reviews),
                1
            )

            product.review_count = (
                len(approved_reviews)
            )

        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                'Review approved successfully!'
            )
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            'success': False,
            'message': str(e)
        })


# ============================================================
# REJECT REVIEW
# ============================================================

@admin_bp.route(
    '/review/<int:review_id>/reject',
    methods=['POST']
)
@admin_required
def reject_review(review_id):

    review = Review.query.get_or_404(
        review_id
    )

    try:

        product = review.product

        db.session.delete(
            review
        )

        db.session.flush()

        approved_reviews = (
            Review.query
            .filter_by(
                product_id=product.id,
                is_approved=True
            )
            .all()
        )

        if approved_reviews:

            total_rating = sum(
                r.rating
                for r in approved_reviews
            )

            product.rating = round(
                total_rating /
                len(approved_reviews),
                1
            )

            product.review_count = (
                len(approved_reviews)
            )

        else:

            product.rating = 0
            product.review_count = 0

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Review rejected!'
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            'success': False,
            'message': str(e)
        })


# ============================================================
# DELETE REVIEW
# ============================================================

@admin_bp.route(
    '/review/<int:review_id>/delete',
    methods=['POST']
)
@admin_required
def delete_review(review_id):

    review = Review.query.get_or_404(
        review_id
    )

    try:

        product = review.product

        db.session.delete(
            review
        )

        db.session.flush()

        approved_reviews = (
            Review.query
            .filter_by(
                product_id=product.id,
                is_approved=True
            )
            .all()
        )

        if approved_reviews:

            total_rating = sum(
                r.rating
                for r in approved_reviews
            )

            product.rating = round(
                total_rating /
                len(approved_reviews),
                1
            )

            product.review_count = (
                len(approved_reviews)
            )

        else:

            product.rating = 0
            product.review_count = 0

        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                'Review deleted successfully!'
            )
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            'success': False,
            'message': str(e)
        })


# ============================================================
# ADMIN CHAT ROUTES - FULLY UPDATED WITH CORRECT URLS
# ============================================================

@admin_bp.route('/chats')
@admin_required
def admin_chats():
    """Admin chat dashboard"""
    status_filter = request.args.get('status', '')
    
    query = ChatConversation.query
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    conversations = query.order_by(
        ChatConversation.updated_at.desc()
    ).all()
    
    statuses = ['Open', 'In Progress', 'Resolved', 'Closed']
    
    return render_template('admin/chats.html', 
                          conversations=conversations, 
                          statuses=statuses,
                          current_status=status_filter)


@admin_bp.route('/chat/<int:conversation_id>')
@admin_required
def chat_detail(conversation_id):
    """Admin view chat detail"""
    conversation = ChatConversation.query.get_or_404(conversation_id)
    return render_template('admin/chat_detail.html', conversation=conversation)


@admin_bp.route('/chat/<int:conversation_id>/reply', methods=['POST'])
@admin_required
def reply_chat(conversation_id):
    """Admin reply to chat"""
    conversation = ChatConversation.query.get_or_404(conversation_id)
    
    message = request.form.get('message', '').strip()
    if not message:
        flash('Message cannot be empty.', 'danger')
        return redirect(url_for('admin.chat_detail', conversation_id=conversation_id))
    
    try:
        chat_message = ChatMessage(
            conversation_id=conversation_id,
            sender_id=current_user.id,
            message=message,
            is_admin_reply=True
        )
        db.session.add(chat_message)
        
        # Update conversation status to In Progress if it was Open
        if conversation.status == 'Open':
            conversation.status = 'In Progress'
        
        conversation.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Reply sent successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error sending reply: {str(e)}', 'danger')
    
    return redirect(url_for('admin.chat_detail', conversation_id=conversation_id))


@admin_bp.route('/chat/<int:conversation_id>/update-status', methods=['POST'])
@admin_required
def update_chat_status(conversation_id):
    """Admin update chat status"""
    conversation = ChatConversation.query.get_or_404(conversation_id)
    
    status = request.form.get('status', '')
    valid_statuses = ['Open', 'In Progress', 'Resolved', 'Closed']
    
    if status not in valid_statuses:
        flash('Invalid status.', 'danger')
        return redirect(url_for('admin.chat_detail', conversation_id=conversation_id))
    
    try:
        conversation.status = status
        conversation.updated_at = datetime.utcnow()
        
        # Add system message
        system_message = ChatMessage(
            conversation_id=conversation_id,
            sender_id=current_user.id,
            message=f"📌 Status changed to: {status}",
            is_admin_reply=False,
            is_system_message=True
        )
        db.session.add(system_message)
        
        db.session.commit()
        flash(f'Chat status updated to {status}!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating status: {str(e)}', 'danger')
    
    return redirect(url_for('admin.chat_detail', conversation_id=conversation_id))


@admin_bp.route('/chat/<int:conversation_id>/close', methods=['POST'])
@admin_required
def close_chat(conversation_id):
    """Admin close chat"""
    conversation = ChatConversation.query.get_or_404(conversation_id)
    
    try:
        conversation.status = 'Closed'
        conversation.updated_at = datetime.utcnow()
        
        system_message = ChatMessage(
            conversation_id=conversation_id,
            sender_id=current_user.id,
            message="🔒 Chat closed.",
            is_admin_reply=False,
            is_system_message=True
        )
        db.session.add(system_message)
        
        db.session.commit()
        flash('Chat closed successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error closing chat: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_chats'))


# ============================================================
# ADMIN COMPLAINT ROUTES
# ============================================================

@admin_bp.route('/complaints')
@admin_required
def admin_complaints():
    """Admin complaints dashboard"""
    status_filter = request.args.get('status', '')
    escalated_filter = request.args.get('escalated', '')
    
    query = Complaint.query
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    if escalated_filter == '1':
        query = query.filter_by(is_escalated=True)
    elif escalated_filter == '0':
        query = query.filter_by(is_escalated=False)
    
    complaints = query.order_by(
        Complaint.created_at.desc()
    ).all()
    
    statuses = ['Pending', 'In Progress', 'Resolved', 'Closed', 'Escalated']
    
    return render_template('admin/complaints.html', 
                          complaints=complaints,
                          statuses=statuses,
                          current_status=status_filter,
                          escalated_filter=escalated_filter)


@admin_bp.route('/complaint/<int:complaint_id>')
@admin_required
def admin_complaint_detail(complaint_id):
    """Admin view complaint detail"""
    complaint = Complaint.query.get_or_404(complaint_id)
    live_chat_requests = LiveChatRequest.query.filter_by(
        complaint_id=complaint_id
    ).all()
    
    return render_template('admin/complaint_detail.html', 
                          complaint=complaint,
                          live_chat_requests=live_chat_requests)


@admin_bp.route('/complaint/<int:complaint_id>/update-status', methods=['POST'])
@admin_required
def update_complaint_status(complaint_id):
    """Admin update complaint status"""
    complaint = Complaint.query.get_or_404(complaint_id)
    
    status = request.form.get('status')
    resolution = request.form.get('resolution', '').strip()
    
    valid_statuses = ['Pending', 'In Progress', 'Resolved', 'Closed', 'Escalated']
    
    if status not in valid_statuses:
        flash('Invalid status.', 'danger')
        return redirect(url_for('admin.admin_complaint_detail', complaint_id=complaint_id))
    
    try:
        complaint.status = status
        
        if status == 'Resolved' and resolution:
            complaint.resolution = resolution
        
        complaint.updated_at = datetime.utcnow()
        
        # Add system message
        system_message = ComplaintMessage(
            complaint_id=complaint_id,
            sender_id=current_user.id,
            message=f"📌 Status updated to: {status}" + (f"\nResolution: {resolution}" if resolution else ""),
            is_admin_reply=False,
            is_system_message=True
        )
        db.session.add(system_message)
        
        db.session.commit()
        
        flash(f'Complaint status updated to {status}!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_complaint_detail', complaint_id=complaint_id))


@admin_bp.route('/complaint/<int:complaint_id>/accept-live-chat', methods=['POST'])
@admin_required
def accept_live_chat(complaint_id):
    """Admin accept live chat request"""
    complaint = Complaint.query.get_or_404(complaint_id)
    
    live_chat_request = LiveChatRequest.query.filter_by(
        complaint_id=complaint_id,
        status='Pending'
    ).first()
    
    if not live_chat_request:
        flash('No pending live chat request found.', 'warning')
        return redirect(url_for('admin.admin_complaint_detail', complaint_id=complaint_id))
    
    try:
        live_chat_request.status = 'Accepted'
        live_chat_request.accepted_at = datetime.utcnow()
        live_chat_request.admin_id = current_user.id
        
        complaint.status = 'In Progress'
        
        # Add system message
        system_message = ComplaintMessage(
            complaint_id=complaint_id,
            sender_id=current_user.id,
            message="🟢 LIVE CHAT ACCEPTED: Admin has accepted the live chat request. You can now chat directly.",
            is_admin_reply=False,
            is_system_message=True
        )
        db.session.add(system_message)
        
        db.session.commit()
        
        flash('Live chat request accepted! You can now chat with the customer.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_complaint_detail', complaint_id=complaint_id))


# ============================================================
# PENDING ORDERS API
# ============================================================

@admin_bp.route(
    '/api/admin/pending-orders-count'
)
@admin_required
def pending_orders_count():

    count = (
        Order.query
        .filter_by(
            order_status='Pending'
        )
        .count()
    )

    return jsonify({
        'success': True,
        'count': count
    })