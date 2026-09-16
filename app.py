import os
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    flash
)

from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from config import config
from database import db, init_login_manager, setup_user_loader

# Import blueprints
from auth import auth_bp
from admin import admin_bp


# ============================================================
# REVIEW IMAGE UPLOAD CONFIG
# ============================================================

REVIEW_IMAGE_FOLDER = 'static/uploads/reviews'

ALLOWED_EXTENSIONS = {
    'png',
    'jpg',
    'jpeg',
    'gif',
    'webp'
}


def allowed_file(filename):
    """Check if file extension is allowed."""
    if not filename:
        return False
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def save_review_image(file):
    """Save review image and return the URL path."""
    
    # Debug print
    print(f"📸 save_review_image called")
    
    if not file:
        print("❌ No file provided")
        return None
    
    if not file.filename:
        print("❌ No filename in file")
        return None
    
    print(f"📸 Filename: {file.filename}")
    
    if not allowed_file(file.filename):
        print(f"❌ File type not allowed: {file.filename}")
        return None
    
    # Get base directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    upload_path = os.path.join(base_dir, 'static', 'uploads', 'reviews')
    
    print(f"📸 Upload path: {upload_path}")
    
    # Create folder if it doesn't exist
    os.makedirs(upload_path, exist_ok=True)
    
    # Secure the filename
    filename = secure_filename(file.filename)
    if not filename:
        print("❌ Failed to secure filename")
        return None
    
    # Add timestamp to filename to make it unique
    name_parts = filename.rsplit('.', 1)
    timestamp = int(datetime.utcnow().timestamp())
    new_filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
    
    file_path = os.path.join(upload_path, new_filename)
    
    print(f"📸 Saving to: {file_path}")
    
    try:
        file.save(file_path)
        print(f"✅ File saved successfully: {file_path}")
        
        # Check if file exists after save
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"📸 File size: {file_size} bytes")
        else:
            print("❌ File not found after save")
            return None
        
        # Return relative URL path for web access
        return f"/static/uploads/reviews/{new_filename}"
        
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================
# CREATE APPLICATION
# ============================================================

def create_app(config_name='default'):

    app = Flask(__name__)

    # ========================================================
    # CONFIGURATION
    # ========================================================

    app.config.from_object(
        config[config_name]
    )

    # ========================================================
    # INITIALIZE EXTENSIONS
    # ========================================================

    db.init_app(app)

    init_login_manager(app)

    # Setup user loader
    setup_user_loader()

    # ========================================================
    # REGISTER BLUEPRINTS
    # ========================================================

    app.register_blueprint(auth_bp)

    app.register_blueprint(admin_bp)

    # ========================================================
    # DATABASE SETUP
    # ========================================================

    with app.app_context():

        db.create_all()

        print(
            "✅ Database tables created successfully!"
        )

        try:
            create_sample_data()

        except Exception as e:

            db.session.rollback()

            print(
                f"⚠️ Sample data error: {e}"
            )

    # ========================================================
    # TEMPLATE FILTERS
    # ========================================================

    @app.template_filter('format_price')
    def format_price(value):
        """Format price with commas."""

        if value is None:
            return "0"

        try:
            return f"{int(float(value)):,}"

        except (ValueError, TypeError):
            return str(value)


    @app.template_filter('currency')
    def currency(value):
        """Format value as Pakistani Rupee."""

        if value is None:
            return "Rs. 0"

        try:
            return f"Rs. {int(float(value)):,}"

        except (ValueError, TypeError):
            return str(value)


    # ========================================================
    # HELPER FUNCTIONS
    # ========================================================

    def get_product_price(product):
        """
        Return the actual selling price.
        Sale price is preferred when available.
        """

        if product.sale_price is not None:
            return float(
                product.sale_price
            )

        return float(
            product.price or 0
        )


    def get_cart():
        """Return session cart in a safe format."""

        cart = session.get(
            'cart',
            {}
        )

        if not isinstance(
            cart,
            dict
        ):
            cart = {}

        return cart


    def cart_count():
        """Return total quantity of products in cart."""

        cart = get_cart()

        total = 0

        for item in cart.values():

            try:
                total += int(
                    item.get(
                        'quantity',
                        0
                    )
                )

            except (
                ValueError,
                TypeError,
                AttributeError
            ):
                pass

        return total


    def calculate_cart_totals():
        """
        Calculate cart subtotal, shipping and total.
        """

        from models import Product

        cart = get_cart()

        subtotal = 0

        cart_items = []

        for product_id, item in cart.items():

            try:
                quantity = int(
                    item.get(
                        'quantity',
                        1
                    )
                )

            except (
                ValueError,
                TypeError,
                AttributeError
            ):
                quantity = 1

            if quantity < 1:
                quantity = 1

            try:
                product = Product.query.get(
                    int(product_id)
                )

            except (
                ValueError,
                TypeError
            ):
                product = None

            if not product:
                continue

            price = get_product_price(
                product
            )

            item_total = (
                price * quantity
            )

            subtotal += item_total

            cart_items.append({
                'product': product,
                'quantity': quantity,
                'price': price,
                'subtotal': item_total
            })

        shipping = (
            0
            if subtotal >= 3000
            else 200
        )

        total = (
            subtotal + shipping
        )

        return (
            cart_items,
            subtotal,
            shipping,
            total
        )


    # ========================================================
    # MAIN ROUTES
    # ========================================================

    @app.route('/')
    def index():

        from models import Product, Category

        featured_products = (
            Product.query
            .filter_by(
                is_featured=True,
                is_active=True
            )
            .limit(8)
            .all()
        )

        bestseller_products = (
            Product.query
            .filter_by(
                is_bestseller=True,
                is_active=True
            )
            .limit(8)
            .all()
        )

        # NEW ARRIVALS
        new_products = (
            Product.query
            .filter_by(
                is_new=True,
                is_active=True
            )
            .order_by(
                Product.created_at.desc()
            )
            .limit(8)
            .all()
        )

        categories = (
            Category.query
            .filter_by(
                is_active=True
            )
            .all()
        )

        return render_template(
            'index.html',
            featured_products=featured_products,
            bestseller_products=bestseller_products,
            new_products=new_products,
            categories=categories
        )


    # ========================================================
    # CLEAR CART ROUTE (For testing)
    # ========================================================

    @app.route('/clear-cart')
    def clear_cart_route():
        """Temporary route to clear cart for testing"""
        session['cart'] = {}
        session.modified = True
        flash('Cart cleared successfully!', 'success')
        return redirect(url_for('index'))


    # ========================================================
    # PRODUCTS
    # ========================================================

    @app.route('/products')
    def products():

        from models import Product, Category

        category_slug = request.args.get(
            'category',
            ''
        ).strip()

        search_query = request.args.get(
            'q',
            ''
        ).strip()

        min_price = request.args.get(
            'min_price',
            ''
        ).strip()

        max_price = request.args.get(
            'max_price',
            ''
        ).strip()

        rating = request.args.get(
            'rating',
            ''
        ).strip()

        in_stock = request.args.get(
            'in_stock',
            ''
        ).strip()

        sort = request.args.get(
            'sort',
            'newest'
        ).strip()

        page = request.args.get(
            'page',
            1,
            type=int
        )

        if page < 1:
            page = 1

        # ----------------------------------------------------
        # Base query
        # ----------------------------------------------------

        query = Product.query.filter_by(
            is_active=True
        )

        # ----------------------------------------------------
        # Category
        # ----------------------------------------------------

        if category_slug:

            category = (
                Category.query
                .filter_by(
                    slug=category_slug,
                    is_active=True
                )
                .first()
            )

            if category:

                query = query.filter(
                    Product.category_id
                    == category.id
                )

        # ----------------------------------------------------
        # Search
        # ----------------------------------------------------

        if search_query:

            search_terms = (
                search_query.split()
            )

            for term in search_terms:

                query = query.filter(
                    or_(
                        Product.name.ilike(
                            f'%{term}%'
                        ),
                        Product.short_description.ilike(
                            f'%{term}%'
                        ),
                        Product.description.ilike(
                            f'%{term}%'
                        ),
                        Product.brand.ilike(
                            f'%{term}%'
                        ),
                        Product.sku.ilike(
                            f'%{term}%'
                        )
                    )
                )

        # ----------------------------------------------------
        # Minimum price
        # ----------------------------------------------------

        if min_price:

            try:

                min_val = float(
                    min_price
                )

                query = query.filter(
                    Product.price >= min_val
                )

            except (
                ValueError,
                TypeError
            ):
                pass

        # ----------------------------------------------------
        # Maximum price
        # ----------------------------------------------------

        if max_price:

            try:

                max_val = float(
                    max_price
                )

                query = query.filter(
                    Product.price <= max_val
                )

            except (
                ValueError,
                TypeError
            ):
                pass

        # ----------------------------------------------------
        # Rating
        # ----------------------------------------------------

        if rating:

            try:

                rating_value = float(
                    rating
                )

                query = query.filter(
                    Product.rating >= rating_value
                )

            except (
                ValueError,
                TypeError
            ):
                pass

        # ----------------------------------------------------
        # Stock
        # ----------------------------------------------------

        if in_stock == '1':

            query = query.filter(
                Product.stock_quantity > 0
            )

        # ----------------------------------------------------
        # Sorting
        # ----------------------------------------------------

        if sort == 'price_low':

            query = query.order_by(
                Product.price.asc()
            )

        elif sort == 'price_high':

            query = query.order_by(
                Product.price.desc()
            )

        elif sort == 'popular':

            query = query.order_by(
                Product.rating.desc()
            )

        elif sort == 'bestselling':

            query = query.order_by(
                Product.is_bestseller.desc()
            )

        else:

            query = query.order_by(
                Product.created_at.desc()
            )

        # ----------------------------------------------------
        # Pagination
        # ----------------------------------------------------

        per_page = 12

        total_products = query.count()

        total_pages = (
            (
                total_products
                + per_page
                - 1
            )
            // per_page
            if total_products > 0
            else 1
        )

        if page > total_pages:
            page = total_pages

        offset = (
            page - 1
        ) * per_page

        products_list = (
            query
            .offset(offset)
            .limit(per_page)
            .all()
        )

        categories = (
            Category.query
            .filter_by(
                is_active=True
            )
            .all()
        )

        return render_template(
            'products.html',
            products=products_list,
            categories=categories,
            total_products=total_products,
            total_pages=total_pages,
            current_page=page,
            category_slug=category_slug,
            search_query=search_query,
            min_price=min_price,
            max_price=max_price,
            rating=rating,
            in_stock=in_stock,
            sort=sort
        )


    # ========================================================
    # PRODUCT DETAIL
    # ========================================================

    @app.route(
        '/product/<int:product_id>'
    )
    def product_detail(product_id):

        from models import Product, Review

        product = (
            Product.query
            .filter_by(
                id=product_id,
                is_active=True
            )
            .first_or_404()
        )

        # Eager load reviews with their images
        reviews = (
            Review.query
            .filter_by(
                product_id=product_id,
                is_approved=True
            )
            .options(db.joinedload(Review.images))
            .order_by(
                Review.created_at.desc()
            )
            .all()
        )

        related_products = []

        # Same category products
        if product.category_id:

            related_products = (
                Product.query
                .filter(
                    Product.category_id
                    == product.category_id,
                    Product.id != product.id,
                    Product.is_active == True
                )
                .limit(4)
                .all()
            )

        # Add other products if needed
        if len(related_products) < 4:

            existing_ids = [
                product.id
            ]

            existing_ids.extend(
                [
                    p.id
                    for p in related_products
                ]
            )

            additional = (
                Product.query
                .filter(
                    Product.id.notin_(
                        existing_ids
                    ),
                    Product.is_active == True
                )
                .limit(
                    4 - len(
                        related_products
                    )
                )
                .all()
            )

            related_products.extend(
                additional
            )

        return render_template(
            'product.html',
            product=product,
            related_products=related_products,
            reviews=reviews
        )


    # ========================================================
    # PRODUCT API
    # ========================================================

    @app.route(
        '/api/product/<int:product_id>'
    )
    def api_product_detail(product_id):

        from models import Product

        product = (
            Product.query
            .filter_by(
                id=product_id,
                is_active=True
            )
            .first()
        )

        if not product:

            return jsonify({
                'success': False,
                'message': 'Product not found'
            }), 404

        return jsonify({

            'success': True,

            'product': {

                'id': product.id,

                'name': product.name,

                'price': float(
                    product.price or 0
                ),

                'sale_price': (
                    float(product.sale_price)
                    if product.sale_price is not None
                    else None
                ),

                'selling_price':
                    get_product_price(
                        product
                    ),

                'short_description': (
                    product.short_description
                    or ''
                ),

                'main_image':
                    product.main_image,

                'rating':
                    float(
                        product.rating or 0
                    ),

                'review_count':
                    product.review_count or 0,

                'stock_quantity':
                    product.stock_quantity or 0
            }
        })


    # ========================================================
    # SET SELECTED ITEMS FOR CHECKOUT (NEW)
    # ========================================================

    @app.route('/api/cart/set-selected', methods=['POST'])
    def set_selected_items():
        """Store selected product IDs in session for checkout"""
        data = request.get_json(silent=True) or {}
        selected_ids = data.get('selected_ids', [])
        
        if not selected_ids or not isinstance(selected_ids, list):
            return jsonify({
                'success': False,
                'message': 'No items selected'
            }), 400
        
        # Store selected IDs in session
        session['selected_items'] = selected_ids
        session.modified = True
        
        return jsonify({
            'success': True,
            'message': f'{len(selected_ids)} items selected',
            'selected_ids': selected_ids
        })


    # ========================================================
    # SUBMIT REVIEW (UPDATED WITH DEBUGGING)
    # ========================================================

    @app.route(
        '/submit-review/<int:product_id>',
        methods=['POST']
    )
    @login_required
    def submit_review(product_id):

        from models import (
            Product,
            Review,
            Order,
            OrderItem,
            ReviewImage
        )

        print("=" * 60)
        print("📝 SUBMIT REVIEW CALLED")
        print("=" * 60)
        print(f"Product ID: {product_id}")
        print(f"User: {current_user.email}")
        print("=" * 60)

        product = (
            Product.query.get_or_404(
                product_id
            )
        )

        # ----------------------------------------------------
        # Check purchase
        # ----------------------------------------------------

        has_purchased = (
            Order.query
            .join(OrderItem)
            .filter(
                Order.user_id
                == current_user.id,

                OrderItem.product_id
                == product_id,

                Order.order_status
                == 'Delivered'
            )
            .first()
        )

        if not has_purchased:

            flash(
                'You can only review products you have purchased and received.',
                'danger'
            )

            return redirect(
                url_for(
                    'product_detail',
                    product_id=product_id
                )
            )

        # ----------------------------------------------------
        # Check existing review
        # ----------------------------------------------------

        existing_review = (
            Review.query
            .filter_by(
                user_id=current_user.id,
                product_id=product_id
            )
            .first()
        )

        if existing_review:

            flash(
                'You have already reviewed this product.',
                'warning'
            )

            return redirect(
                url_for(
                    'product_detail',
                    product_id=product_id
                )
            )

        # ----------------------------------------------------
        # Form data
        # ----------------------------------------------------

        rating = request.form.get(
            'rating',
            type=int
        )

        comment = request.form.get(
            'comment',
            ''
        ).strip()

        print(f"📝 Rating: {rating}")
        print(f"📝 Comment: {comment[:50] if comment else 'Empty'}...")

        if (
            rating is None
            or rating < 1
            or rating > 5
        ):

            flash(
                'Please provide a valid rating (1-5).',
                'danger'
            )

            return redirect(
                url_for(
                    'product_detail',
                    product_id=product_id
                )
            )

        if not comment:

            flash(
                'Please write a review comment.',
                'danger'
            )

            return redirect(
                url_for(
                    'product_detail',
                    product_id=product_id
                )
            )

        # ----------------------------------------------------
        # Check files in request
        # ----------------------------------------------------
        
        print("-" * 40)
        print("📸 CHECKING FILES IN REQUEST")
        print(f"request.files: {request.files}")
        print(f"request.files keys: {list(request.files.keys())}")
        
        if 'review_images' in request.files:
            files = request.files.getlist('review_images')
            print(f"Number of files: {len(files)}")
            for i, file in enumerate(files):
                print(f"  File {i}: filename='{file.filename}', content_type='{file.content_type}'")
                
                # Check if file is empty
                if file and file.filename:
                    file.seek(0, 2)  # Go to end
                    size = file.tell()
                    file.seek(0)  # Go back to start
                    print(f"    File size: {size} bytes")
                    
                    if size == 0:
                        print(f"    ❌ File is empty!")
        else:
            print("❌ 'review_images' NOT found in request.files")
        print("-" * 40)

        # ----------------------------------------------------
        # Save review
        # ----------------------------------------------------

        try:

            review = Review(
                user_id=current_user.id,
                product_id=product_id,
                rating=rating,
                comment=comment,
                is_approved=True
            )

            db.session.add(review)

            db.session.flush()

            print(f"📝 Review created with ID: {review.id}")

            # Handle review images
            uploaded_count = 0
            if 'review_images' in request.files:

                files = request.files.getlist(
                    'review_images'
                )

                for file in files:

                    if (
                        file
                        and file.filename
                    ):
                        print(f"📸 Processing: {file.filename}")
                        
                        uploaded_path = save_review_image(file)

                        if uploaded_path:
                            uploaded_count += 1
                            review_image = ReviewImage(
                                review_id=review.id,
                                image_url=uploaded_path
                            )

                            db.session.add(review_image)
                            print(f"✅ Image saved to database: {uploaded_path}")
                        else:
                            print(f"❌ Failed to save image: {file.filename}")
                    else:
                        print(f"⚠️ Invalid file object")

            print(f"📸 Total images uploaded: {uploaded_count}")

            # Recalculate rating
            approved_reviews = (
                Review.query
                .filter_by(
                    product_id=product_id,
                    is_approved=True
                )
                .all()
            )

            if approved_reviews:

                total_rating = sum(
                    review_item.rating
                    for review_item
                    in approved_reviews
                )

                product.rating = round(
                    total_rating
                    / len(
                        approved_reviews
                    ),
                    1
                )

                product.review_count = (
                    len(
                        approved_reviews
                    )
                )

            db.session.commit()

            flash(
                f'Thank you for your review! {uploaded_count} image(s) uploaded.',
                'success'
            )

        except Exception as e:

            db.session.rollback()

            print(
                f"❌ Review error: {e}"
            )
            import traceback
            traceback.print_exc()

            flash(
                'Unable to submit your review. Please try again.',
                'danger'
            )

        return redirect(
            url_for(
                'product_detail',
                product_id=product_id
            )
        )


    # ========================================================
    # DELETE CUSTOMER REVIEW
    # ========================================================

    @app.route(
        '/delete-review/<int:review_id>',
        methods=['POST']
    )
    @login_required
    def delete_customer_review(review_id):

        from models import (
            Review,
            ReviewImage,
            Product
        )

        review = (
            Review.query.get_or_404(
                review_id
            )
        )

        if (
            review.user_id
            != current_user.id
            and current_user.role
            != 'admin'
        ):

            flash(
                'You do not have permission to delete this review.',
                'danger'
            )

            return redirect(
                url_for(
                    'product_detail',
                    product_id=review.product_id
                )
            )

        product_id = review.product_id

        product = Product.query.get(
            product_id
        )

        try:

            ReviewImage.query.filter_by(
                review_id=review_id
            ).delete()

            db.session.delete(
                review
            )

            approved_reviews = (
                Review.query
                .filter_by(
                    product_id=product_id,
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
                    total_rating
                    / len(
                        approved_reviews
                    ),
                    1
                )

                product.review_count = (
                    len(
                        approved_reviews
                    )
                )

            else:

                product.rating = 0

                product.review_count = 0

            db.session.commit()

            flash(
                'Review deleted successfully!',
                'success'
            )

        except Exception as e:

            db.session.rollback()

            flash(
                f'Error deleting review: {str(e)}',
                'danger'
            )

        return redirect(
            url_for(
                'product_detail',
                product_id=product_id
            )
        )


    # ========================================================
    # CART PAGE
    # ========================================================

    @app.route('/cart')
    def cart():

        (
            cart_items,
            subtotal,
            shipping,
            total
        ) = calculate_cart_totals()

        return render_template(
            'cart.html',
            cart_items=cart_items,
            subtotal=subtotal,
            shipping=shipping,
            total=total
        )


    # ========================================================
    # ADD TO CART
    # ========================================================

    @app.route(
        '/api/cart/add',
        methods=['POST']
    )
    def add_to_cart():

        from models import Product

        data = request.get_json(
            silent=True
        ) or {}

        product_id = data.get(
            'product_id'
        )

        quantity = data.get(
            'quantity',
            1
        )

        try:

            product_id = int(
                product_id
            )

        except (
            ValueError,
            TypeError
        ):

            return jsonify({
                'success': False,
                'message': 'Invalid product ID'
            }), 400

        try:

            quantity = int(
                quantity
            )

        except (
            ValueError,
            TypeError
        ):

            quantity = 1

        if quantity < 1:
            quantity = 1

        product = Product.query.get(
            product_id
        )

        if (
            not product
            or not product.is_active
        ):

            return jsonify({
                'success': False,
                'message': 'Product not found'
            }), 404

        if not product.is_in_stock():

            return jsonify({
                'success': False,
                'message': 'Product is out of stock'
            }), 400

        cart_data = get_cart()

        product_key = str(
            product_id
        )

        current_quantity = 0

        if product_key in cart_data:

            try:

                current_quantity = int(
                    cart_data[
                        product_key
                    ].get(
                        'quantity',
                        0
                    )
                )

            except (
                ValueError,
                TypeError
            ):

                current_quantity = 0

        new_quantity = (
            current_quantity
            + quantity
        )

        if (
            new_quantity
            > product.stock_quantity
        ):

            return jsonify({
                'success': False,
                'message': (
                    f'Only {product.stock_quantity} units '
                    f'are available.'
                )
            }), 400

        cart_data[product_key] = {
            'quantity': new_quantity,
            'price': get_product_price(
                product
            )
        }

        session['cart'] = cart_data

        session.modified = True

        (
            _,
            subtotal,
            shipping,
            total
        ) = calculate_cart_totals()

        return jsonify({

            'success': True,

            'message':
                f'{product.name} added to cart!',

            'cart_count':
                cart_count(),

            'cart_subtotal':
                subtotal,

            'cart_shipping':
                shipping,

            'cart_total':
                total
        })


    # ========================================================
    # BUY NOW (FIXED - Replaces entire cart)
    # ========================================================

    @app.route(
        '/api/cart/buy-now',
        methods=['POST']
    )
    def buy_now():

        from models import Product

        data = request.get_json(
            silent=True
        ) or {}

        product_id = data.get(
            'product_id'
        )

        quantity = data.get(
            'quantity',
            1
        )

        try:

            product_id = int(
                product_id
            )

        except (
            ValueError,
            TypeError
        ):

            return jsonify({
                'success': False,
                'message': 'Invalid product ID'
            }), 400

        try:

            quantity = int(
                quantity
            )

        except (
            ValueError,
            TypeError
        ):

            quantity = 1

        if quantity < 1:
            quantity = 1

        product = Product.query.get(
            product_id
        )

        if (
            not product
            or not product.is_active
        ):

            return jsonify({
                'success': False,
                'message': 'Product not found'
            }), 404

        if not product.is_in_stock():

            return jsonify({
                'success': False,
                'message': 'Product is out of stock'
            }), 400

        if quantity > product.stock_quantity:

            return jsonify({
                'success': False,
                'message': (
                    f'Only {product.stock_quantity} units '
                    f'are available.'
                )
            }), 400

        # =====================================================
        # FIX: Replace entire cart instead of adding to it
        # =====================================================
        session['cart'] = {
            str(product_id): {
                'quantity': quantity,
                'price': get_product_price(
                    product
                )
            }
        }

        # Clear any selected items
        session.pop('selected_items', None)
        session.modified = True

        return jsonify({
            'success': True,
            'message':
                'Product ready for checkout.',
            'redirect_url':
                url_for('checkout')
        })


    # ========================================================
    # UPDATE CART
    # ========================================================

    @app.route(
        '/api/cart/update',
        methods=['POST']
    )
    def update_cart():

        from models import Product

        data = request.get_json(
            silent=True
        ) or {}

        product_id = data.get(
            'product_id'
        )

        quantity = data.get(
            'quantity',
            1
        )

        try:

            product_id = int(
                product_id
            )

        except (
            ValueError,
            TypeError
        ):

            return jsonify({
                'success': False,
                'message': 'Invalid product ID'
            }), 400

        try:

            quantity = int(
                quantity
            )

        except (
            ValueError,
            TypeError
        ):

            quantity = 1

        cart_data = get_cart()

        product_key = str(
            product_id
        )

        if product_key not in cart_data:

            return jsonify({
                'success': False,
                'message': 'Product not in cart'
            }), 404

        if quantity <= 0:

            del cart_data[
                product_key
            ]

        else:

            product = Product.query.get(
                product_id
            )

            if not product:

                del cart_data[
                    product_key
                ]

            elif (
                quantity
                > product.stock_quantity
            ):

                return jsonify({
                    'success': False,
                    'message': (
                        f'Only {product.stock_quantity} units '
                        f'are available.'
                    )
                }), 400

            else:

                cart_data[
                    product_key
                ]['quantity'] = quantity

                cart_data[
                    product_key
                ]['price'] = (
                    get_product_price(
                        product
                    )
                )

        session['cart'] = cart_data

        session.modified = True

        (
            _,
            subtotal,
            shipping,
            total
        ) = calculate_cart_totals()

        return jsonify({
            'success': True,
            'cart_count':
                cart_count(),
            'subtotal':
                subtotal,
            'shipping':
                shipping,
            'total':
                total
        })


    # ========================================================
    # REMOVE FROM CART
    # ========================================================

    @app.route(
        '/api/cart/remove',
        methods=['POST']
    )
    def remove_from_cart():

        data = request.get_json(
            silent=True
        ) or {}

        product_id = data.get(
            'product_id'
        )

        try:

            product_id = int(
                product_id
            )

        except (
            ValueError,
            TypeError
        ):

            return jsonify({
                'success': False,
                'message': 'Invalid product ID'
            }), 400

        cart_data = get_cart()

        product_key = str(
            product_id
        )

        if product_key in cart_data:

            del cart_data[
                product_key
            ]

        session['cart'] = cart_data

        session.modified = True

        (
            _,
            subtotal,
            shipping,
            total
        ) = calculate_cart_totals()

        return jsonify({
            'success': True,
            'message':
                'Item removed from cart.',
            'cart_count':
                cart_count(),
            'subtotal':
                subtotal,
            'shipping':
                shipping,
            'total':
                total
        })


    # ========================================================
    # CLEAR CART API
    # ========================================================

    @app.route(
        '/api/cart/clear',
        methods=['POST']
    )
    def clear_cart():

        session['cart'] = {}
        session.pop('selected_items', None)
        session.modified = True

        return jsonify({
            'success': True,
            'message':
                'Cart cleared.'
        })


    # ========================================================
    # CART COUNT API
    # ========================================================

    @app.route(
        '/api/cart/count'
    )
    def api_cart_count():

        return jsonify({
            'success': True,
            'count':
                cart_count()
        })


    # ========================================================
    # WISHLIST PAGE
    # ========================================================

    @app.route('/wishlist')
    @login_required
    def wishlist():

        from models import Wishlist

        wishlist_items = (
            Wishlist.query
            .filter_by(
                user_id=current_user.id
            )
            .all()
        )

        return render_template(
            'wishlist.html',
            wishlist_items=wishlist_items
        )


    # ========================================================
    # ADD TO WISHLIST
    # ========================================================

    @app.route(
        '/api/wishlist/add',
        methods=['POST']
    )
    @login_required
    def add_to_wishlist():

        from models import (
            Wishlist,
            Product
        )

        data = request.get_json(
            silent=True
        ) or {}

        product_id = data.get(
            'product_id'
        )

        try:

            product_id = int(
                product_id
            )

        except (
            ValueError,
            TypeError
        ):

            return jsonify({
                'success': False,
                'message':
                    'Invalid product ID'
            }), 400

        product = Product.query.get(
            product_id
        )

        if (
            not product
            or not product.is_active
        ):

            return jsonify({
                'success': False,
                'message':
                    'Product not found'
            }), 404

        existing = (
            Wishlist.query
            .filter_by(
                user_id=current_user.id,
                product_id=product_id
            )
            .first()
        )

        if existing:

            return jsonify({
                'success': False,
                'message':
                    'Product already in wishlist'
            })

        try:

            wishlist_item = Wishlist(
                user_id=current_user.id,
                product_id=product_id
            )

            db.session.add(
                wishlist_item            )

            db.session.commit()

            return jsonify({
                'success': True,
                'message':
                    f'{product.name} added to wishlist!'
            })

        except Exception as e:

            db.session.rollback()

            print(
                f"Wishlist add error: {e}"
            )

            return jsonify({
                'success': False,
                'message':
                    'Unable to add to wishlist.'
            }), 500


    # ========================================================
    # REMOVE FROM WISHLIST
    # ========================================================

    @app.route(
        '/api/wishlist/remove',
        methods=['POST']
    )
    @login_required
    def remove_from_wishlist():

        from models import Wishlist

        data = request.get_json(
            silent=True
        ) or {}

        product_id = data.get(
            'product_id'
        )

        try:

            product_id = int(
                product_id
            )

        except (
            ValueError,
            TypeError
        ):

            return jsonify({
                'success': False,
                'message':
                    'Invalid product ID'
            }), 400

        wishlist_item = (
            Wishlist.query
            .filter_by(
                user_id=current_user.id,
                product_id=product_id
            )
            .first()
        )

        if not wishlist_item:

            return jsonify({
                'success': False,
                'message':
                    'Item not in wishlist'
            })

        try:

            db.session.delete(
                wishlist_item
            )

            db.session.commit()

            return jsonify({
                'success': True,
                'message':
                    'Removed from wishlist!'
            })

        except Exception as e:

            db.session.rollback()

            print(
                f"Wishlist remove error: {e}"
            )

            return jsonify({
                'success': False,
                'message':
                    'Unable to remove item.'
            }), 500


    # ========================================================
    # WISHLIST COUNT
    # ========================================================

    @app.route(
        '/api/wishlist/count'
    )
    @login_required
    def wishlist_count():

        from models import Wishlist

        count = (
            Wishlist.query
            .filter_by(
                user_id=current_user.id
            )
            .count()
        )

        return jsonify({
            'success': True,
            'count': count
        })


    # ========================================================
    # WISHLIST STATUS
    # ========================================================

    @app.route(
        '/api/wishlist/status/<int:product_id>'
    )
    @login_required
    def wishlist_status(product_id):

        from models import Wishlist

        exists = (
            Wishlist.query
            .filter_by(
                user_id=current_user.id,
                product_id=product_id
            )
            .first()
            is not None
        )

        return jsonify({
            'success': True,
            'in_wishlist': exists
        })


    # ========================================================
    # WISHLIST IDS
    # ========================================================

    @app.route(
        '/api/wishlist/ids'
    )
    @login_required
    def wishlist_ids():

        from models import Wishlist

        ids = [
            item.product_id
            for item in (
                Wishlist.query
                .filter_by(
                    user_id=current_user.id
                )
                .all()
            )
        ]

        return jsonify({
            'success': True,
            'ids': ids
        })


    # ========================================================
    # CHECKOUT (UPDATED - Only selected items)
    # ========================================================

    @app.route('/checkout')
    def checkout():
        """Checkout page - only shows selected items"""
        
        # Get selected items from session
        selected_ids = session.get('selected_items', [])
        
        if not selected_ids:
            flash(
                'Please select items from your cart first.',
                'warning'
            )
            return redirect(url_for('cart'))
        
        # Get all cart items
        cart_data = get_cart()
        
        if not cart_data:
            flash(
                'Your cart is empty. Please add some products first.',
                'warning'
            )
            return redirect(url_for('products'))
        
        # Filter cart items to only selected ones
        filtered_cart = {}
        for product_id, item in cart_data.items():
            if int(product_id) in selected_ids:
                filtered_cart[product_id] = item
        
        if not filtered_cart:
            flash(
                'Selected items are no longer available in your cart.',
                'warning'
            )
            session.pop('selected_items', None)
            return redirect(url_for('cart'))
        
        # Temporarily replace cart with filtered items for calculation
        original_cart = session.get('cart', {})
        session['cart'] = filtered_cart
        session.modified = True
        
        # Calculate totals for selected items
        (cart_items, subtotal, shipping, total) = calculate_cart_totals()
        
        # Restore original cart
        session['cart'] = original_cart
        session.modified = True
        
        if not cart_items:
            flash(
                'Selected items are no longer available.',
                'warning'
            )
            session.pop('selected_items', None)
            return redirect(url_for('cart'))
        
        return render_template(
            'checkout.html',
            cart_items=cart_items,
            subtotal=subtotal,
            shipping=shipping,
            total=total,
            selected_ids=selected_ids
        )


    # ========================================================
    # PLACE ORDER (UPDATED - Only selected items)
    # ========================================================

    @app.route(
        '/place-order',
        methods=['POST']
    )
    def place_order():

        from models import (
            Product,
            Order,
            OrderItem
        )

        # Get selected items from session
        selected_ids = session.get('selected_items', [])
        
        if not selected_ids:
            flash(
                'Please select items from your cart first.',
                'warning'
            )
            return redirect(url_for('cart'))
        
        cart_data = get_cart()

        if not cart_data:
            flash(
                'Your cart is empty.',
                'warning'
            )
            return redirect(url_for('products'))
        
        # Filter cart to only selected items
        filtered_cart = {}
        for product_id, item in cart_data.items():
            if int(product_id) in selected_ids:
                filtered_cart[product_id] = item
        
        if not filtered_cart:
            flash(
                'Selected items are no longer available.',
                'warning'
            )
            session.pop('selected_items', None)
            return redirect(url_for('cart'))

        # ----------------------------------------------------
        # Customer information
        # ----------------------------------------------------

        customer_name = request.form.get(
            'full_name',
            ''
        ).strip()

        phone = request.form.get(
            'phone',
            ''
        ).strip()

        email = request.form.get(
            'email',
            ''
        ).strip()

        address = request.form.get(
            'address',
            ''
        ).strip()

        city = request.form.get(
            'city',
            ''
        ).strip()

        province = request.form.get(
            'province',
            ''
        ).strip()

        postal_code = request.form.get(
            'postal_code',
            ''
        ).strip()

        notes = request.form.get(
            'notes',
            ''
        ).strip()

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        if not all([
            customer_name,
            phone,
            email,
            address,
            city,
            province
        ]):

            flash(
                'Please fill in all required fields.',
                'danger'
            )

            return redirect(
                url_for('checkout')
            )

        # ----------------------------------------------------
        # Prepare order items (only from filtered cart)
        # ----------------------------------------------------

        subtotal = 0
        order_items_data = []

        for product_id, item in filtered_cart.items():

            try:
                product_id_int = int(product_id)
            except (ValueError, TypeError):
                flash('Invalid product in cart.', 'danger')
                return redirect(url_for('cart'))

            try:
                quantity = int(item.get('quantity', 1))
            except (ValueError, TypeError):
                quantity = 1

            if quantity < 1:
                flash('Invalid product quantity.', 'danger')
                return redirect(url_for('cart'))

            product = Product.query.get(product_id_int)

            if not product:
                flash('A product in your cart no longer exists.', 'danger')
                return redirect(url_for('cart'))

            if not product.is_active:
                flash(f'{product.name} is no longer available.', 'danger')
                return redirect(url_for('cart'))

            if not product.is_in_stock():
                flash(f'{product.name} is out of stock.', 'danger')
                return redirect(url_for('cart'))

            if product.stock_quantity < quantity:
                flash(
                    f'Not enough stock for {product.name}. Available: {product.stock_quantity}',
                    'danger'
                )
                return redirect(url_for('cart'))

            price = get_product_price(product)
            item_total = price * quantity
            subtotal += item_total

            order_items_data.append({
                'product': product,
                'quantity': quantity,
                'price': price,
                'subtotal': item_total
            })

        # ----------------------------------------------------
        # Shipping
        # ----------------------------------------------------

        shipping = 0 if subtotal >= 3000 else 200
        total = subtotal + shipping

        # ----------------------------------------------------
        # Order number
        # ----------------------------------------------------

        order_number = (
            f"ORD-"
            f"{datetime.now().strftime('%Y%m%d')}-"
            f"{datetime.now().strftime('%H%M%S%f')}"
        )

        try:
            # Create order
            order = Order(
                order_number=order_number,
                user_id=current_user.id if current_user.is_authenticated else None,
                customer_name=customer_name,
                phone=phone,
                email=email,
                address=address,
                city=city,
                province=province,
                postal_code=postal_code,
                notes=notes,
                subtotal=subtotal,
                shipping_fee=shipping,
                total_amount=total,
                payment_method='COD',
                order_status='Pending'
            )

            db.session.add(order)
            db.session.flush()

            # Order items + stock
            for data in order_items_data:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=data['product'].id,
                    product_name=data['product'].name,
                    quantity=data['quantity'],
                    price=data['price'],
                    subtotal=data['subtotal']
                )
                db.session.add(order_item)
                data['product'].stock_quantity -= data['quantity']

            # Remove only selected items from cart
            cart_data = get_cart()
            for product_id in selected_ids:
                if str(product_id) in cart_data:
                    del cart_data[str(product_id)]
            
            # Clear selected items from session
            session.pop('selected_items', None)
            session['cart'] = cart_data
            session.modified = True

            db.session.commit()

            flash(
                f'Order placed successfully! Your order number is {order_number}',
                'success'
            )

            return redirect(url_for('order_success', order_id=order.id))

        except Exception as e:
            db.session.rollback()
            print(f"Order error: {e}")
            flash('Error placing order. Please try again.', 'danger')
            return redirect(url_for('checkout'))


    # ========================================================
    # ORDER SUCCESS
    # ========================================================

    @app.route('/order-success')
    def order_success():

        from models import Order

        order_id = request.args.get(
            'order_id',
            type=int
        )

        if not order_id:

            flash(
                'Order not found.',
                'danger'
            )

            return redirect(
                url_for('index')
            )

        order = Order.query.get(
            order_id
        )

        if not order:

            flash(
                'Order not found.',
                'danger'
            )

            return redirect(
                url_for('index')
            )

        if current_user.is_authenticated:

            if (
                order.user_id is not None
                and order.user_id
                != current_user.id
                and current_user.role
                != 'admin'
            ):

                flash(
                    'You do not have permission to view this order.',
                    'danger'
                )

                return redirect(
                    url_for('index')
                )

        return render_template(
            'order_success.html',
            order=order
        )


    # ========================================================
    # USER ORDERS
    # ========================================================

    @app.route('/orders')
    @login_required
    def orders():

        from models import Order

        user_orders = (
            Order.query
            .filter_by(
                user_id=current_user.id
            )
            .order_by(
                Order.created_at.desc()
            )
            .all()
        )

        return render_template(
            'orders.html',
            orders=user_orders
        )


    # ========================================================
    # ORDER DETAIL
    # ========================================================

    @app.route(
        '/order/<int:order_id>'
    )
    @login_required
    def order_detail(order_id):

        from models import Order

        order = Order.query.get_or_404(
            order_id
        )

        if (
            order.user_id
            != current_user.id
            and current_user.role
            != 'admin'
        ):

            flash(
                'You do not have permission to view this order.',
                'danger'
            )

            return redirect(
                url_for('orders')
            )

        return render_template(
            'order_detail.html',
            order=order
        )


    # ========================================================
    # PRODUCT SEARCH API
    # ========================================================

    @app.route(
        '/api/products/search'
    )
    def api_search_products():

        from models import Product

        search_query = request.args.get(
            'q',
            ''
        ).strip()

        if not search_query:
            return jsonify([])

        products_list = (
            Product.query
            .filter(
                or_(
                    Product.name.ilike(
                        f'%{search_query}%'
                    ),
                    Product.brand.ilike(
                        f'%{search_query}%'
                    ),
                    Product.sku.ilike(
                        f'%{search_query}%'
                    )
                ),
                Product.is_active == True
            )
            .limit(10)
            .all()
        )

        results = []

        for product in products_list:

            results.append({

                'id':
                    product.id,

                'name':
                    product.name,

                'price':
                    float(
                        product.price or 0
                    ),

                'sale_price': (
                    float(product.sale_price)
                    if product.sale_price
                    is not None
                    else None
                ),

                'selling_price':
                    get_product_price(
                        product
                    ),

                'image':
                    product.main_image,

                'url':
                    url_for(
                        'product_detail',
                        product_id=product.id
                    )
            })

        return jsonify(
            results
        )


    # ========================================================
    # CHAT / HELP DESK ROUTES
    # ========================================================

    @app.route('/help')
    def help():
        """Help page with chat options"""
        return render_template('help.html')


    @app.route('/chat')
    @login_required
    def chat():
        """User chat dashboard"""
        from models import ChatConversation
        
        conversations = ChatConversation.query.filter_by(
            user_id=current_user.id
        ).order_by(ChatConversation.updated_at.desc()).all()
        
        return render_template('chat.html', conversations=conversations)


    @app.route('/chat/new', methods=['GET', 'POST'])
    @login_required
    def new_chat():
        """Start a new chat conversation"""
        from models import ChatConversation, ChatMessage, Order
        
        if request.method == 'POST':
            subject = request.form.get('subject', '').strip()
            message = request.form.get('message', '').strip()
            category = request.form.get('category', 'Other')
            order_id = request.form.get('order_id', type=int)
            
            if not subject:
                flash('Please enter a subject.', 'danger')
                return redirect(url_for('new_chat'))
            
            if not message:
                flash('Please enter your message.', 'danger')
                return redirect(url_for('new_chat'))
            
            try:
                conversation = ChatConversation(
                    user_id=current_user.id,
                    subject=subject,
                    category=category,
                    order_id=order_id if order_id else None,
                    status='Open'
                )
                db.session.add(conversation)
                db.session.flush()
                
                chat_message = ChatMessage(
                    conversation_id=conversation.id,
                    sender_id=current_user.id,
                    message=message,
                    is_admin_reply=False
                )
                db.session.add(chat_message)
                db.session.commit()
                
                flash('Your message has been sent! Our support team will get back to you soon.', 'success')
                return redirect(url_for('chat'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {str(e)}', 'danger')
                
        # GET request - show form
        orders = Order.query.filter_by(
            user_id=current_user.id
        ).order_by(Order.created_at.desc()).all()
        
        return render_template('new_chat.html', orders=orders)


    @app.route('/chat/<int:conversation_id>')
    @login_required
    def chat_detail(conversation_id):
        """View chat conversation"""
        from models import ChatConversation, ChatMessage
        
        conversation = ChatConversation.query.get_or_404(conversation_id)
        
        # Check if user owns this conversation
        if conversation.user_id != current_user.id and current_user.role != 'admin':
            flash('You do not have permission to view this conversation.', 'danger')
            return redirect(url_for('chat'))
        
        # Mark messages as read
        ChatMessage.query.filter_by(
            conversation_id=conversation_id,
            is_read=False
        ).filter(ChatMessage.sender_id != current_user.id).update({'is_read': True})
        db.session.commit()
        
        return render_template('chat_detail.html', conversation=conversation)


    @app.route('/chat/<int:conversation_id>/send', methods=['POST'])
    @login_required
    def send_chat_message(conversation_id):
        """Send a message in chat"""
        from models import ChatConversation, ChatMessage
        
        conversation = ChatConversation.query.get_or_404(conversation_id)
        
        # Check if user owns this conversation
        if conversation.user_id != current_user.id and current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        message = request.form.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'message': 'Message cannot be empty'}), 400
        
        try:
            chat_message = ChatMessage(
                conversation_id=conversation_id,
                sender_id=current_user.id,
                message=message,
                is_admin_reply=(current_user.role == 'admin')
            )
            db.session.add(chat_message)
            
            # Update conversation timestamp
            conversation.updated_at = datetime.utcnow()
            
            # If user is replying, reopen the conversation if it was closed
            if current_user.role == 'admin' and conversation.status == 'Closed':
                conversation.status = 'Open'
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': {
                    'id': chat_message.id,
                    'text': chat_message.message,
                    'sender': current_user.full_name,
                    'is_admin': chat_message.is_admin_reply,
                    'time': chat_message.created_at.strftime('%I:%M %p')
                }
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500


    @app.route('/api/chat/unread-count')
    @login_required
    def chat_unread_count():
        """Get unread message count for user"""
        from models import ChatConversation, ChatMessage
        
        # For admin - count all unread messages from users
        if current_user.role == 'admin':
            count = ChatMessage.query.filter_by(
                is_read=False,
                is_admin_reply=False
            ).count()
        else:
            # For user - count unread admin replies
            user_conversations = ChatConversation.query.filter_by(user_id=current_user.id).all()
            conv_ids = [c.id for c in user_conversations]
            count = ChatMessage.query.filter(
                ChatMessage.conversation_id.in_(conv_ids),
                ChatMessage.is_read == False,
                ChatMessage.is_admin_reply == True
            ).count()
        
        return jsonify({'success': True, 'count': count})


    # ========================================================
    # COMPLAINT / TICKET ROUTES
    # ========================================================

    @app.route('/complaints')
    @login_required
    def complaints():
        """View all complaints for the current user"""
        from models import Complaint
        
        user_complaints = Complaint.query.filter_by(
            user_id=current_user.id
        ).order_by(Complaint.created_at.desc()).all()
        
        return render_template('complaints.html', complaints=user_complaints)


    @app.route('/complaint/new', methods=['GET', 'POST'])
    @login_required
    def new_complaint():
        """Create a new complaint"""
        from models import Complaint, ComplaintMessage, Order
        
        if request.method == 'POST':
            order_number = request.form.get('order_number', '').strip()
            subject = request.form.get('subject', '').strip()
            description = request.form.get('description', '').strip()
            category = request.form.get('category', 'General')
            priority = request.form.get('priority', 'Normal')
            
            if not subject:
                flash('Please enter a subject.', 'danger')
                return redirect(url_for('new_complaint'))
            
            if not description:
                flash('Please describe your issue.', 'danger')
                return redirect(url_for('new_complaint'))
            
            # Find order if order number provided
            order_id = None
            if order_number:
                order = Order.query.filter_by(
                    order_number=order_number,
                    user_id=current_user.id
                ).first()
                if order:
                    order_id = order.id
            
            try:
                complaint = Complaint(
                    user_id=current_user.id,
                    order_id=order_id,
                    order_number=order_number if order_id else None,
                    subject=subject,
                    description=description,
                    category=category,
                    priority=priority,
                    status='Pending',
                    is_escalated=False
                )
                db.session.add(complaint)
                db.session.flush()
                
                # Add initial message
                message = ComplaintMessage(
                    complaint_id=complaint.id,
                    sender_id=current_user.id,
                    message=description,
                    is_admin_reply=False,
                    is_system_message=False
                )
                db.session.add(message)
                
                # Add system message about 24 hours wait
                system_message = ComplaintMessage(
                    complaint_id=complaint.id,
                    sender_id=current_user.id,
                    message="📌 Your complaint has been registered. Our support team will respond within 24 hours. You will be able to request a live chat if you don't receive a response within 24 hours.",
                    is_admin_reply=False,
                    is_system_message=True
                )
                db.session.add(system_message)
                
                db.session.commit()
                
                flash('Your complaint has been registered successfully! Our team will respond within 24 hours.', 'success')
                return redirect(url_for('complaint_detail', complaint_id=complaint.id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {str(e)}', 'danger')
        
        # GET request - show form
        orders = Order.query.filter_by(
            user_id=current_user.id
        ).order_by(Order.created_at.desc()).all()
        
        return render_template('new_complaint.html', orders=orders)


    @app.route('/complaint/<int:complaint_id>')
    @login_required
    def complaint_detail(complaint_id):
        """View complaint details"""
        from models import Complaint, LiveChatRequest
        
        complaint = Complaint.query.get_or_404(complaint_id)
        
        if complaint.user_id != current_user.id and current_user.role != 'admin':
            flash('You do not have permission to view this complaint.', 'danger')
            return redirect(url_for('complaints'))
        
        # Check if live chat is already requested
        live_chat_request = LiveChatRequest.query.filter_by(
            complaint_id=complaint_id,
            user_id=current_user.id
        ).first()
        
        return render_template('complaint_detail.html', 
                              complaint=complaint,
                              live_chat_request=live_chat_request)


    @app.route('/complaint/<int:complaint_id>/message', methods=['POST'])
    @login_required
    def add_complaint_message(complaint_id):
        """Add a message to a complaint"""
        from models import Complaint, ComplaintMessage
        
        complaint = Complaint.query.get_or_404(complaint_id)
        
        if complaint.user_id != current_user.id and current_user.role != 'admin':
            flash('You do not have permission to reply.', 'danger')
            return redirect(url_for('complaints'))
        
        message = request.form.get('message', '').strip()
        
        if not message:
            flash('Please enter a message.', 'danger')
            return redirect(url_for('complaint_detail', complaint_id=complaint_id))
        
        try:
            complaint_message = ComplaintMessage(
                complaint_id=complaint_id,
                sender_id=current_user.id,
                message=message,
                is_admin_reply=(current_user.role == 'admin')
            )
            db.session.add(complaint_message)
            
            # Update complaint status if admin replies
            if current_user.role == 'admin' and complaint.status == 'Pending':
                complaint.status = 'In Progress'
            
            # If user replies after escalation, update status
            if current_user.role != 'admin' and complaint.is_escalated:
                complaint.status = 'In Progress'
            
            complaint.updated_at = datetime.utcnow()
            db.session.commit()
            
            flash('Message sent successfully!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
        
        return redirect(url_for('complaint_detail', complaint_id=complaint_id))


    @app.route('/complaint/<int:complaint_id>/request-live-chat', methods=['POST'])
    @login_required
    def request_live_chat(complaint_id):
        """Request live chat after 24 hours"""
        from models import Complaint, LiveChatRequest, ComplaintMessage
        
        complaint = Complaint.query.get_or_404(complaint_id)
        
        if complaint.user_id != current_user.id:
            flash('You do not have permission.', 'danger')
            return redirect(url_for('complaints'))
        
        if not complaint.can_escalate():
            remaining = 86400 - complaint.get_time_elapsed().total_seconds()
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            flash(f'You need to wait {hours}h {minutes}m before requesting live chat. 24 hours must pass since complaint creation.', 'warning')
            return redirect(url_for('complaint_detail', complaint_id=complaint_id))
        
        if complaint.status == 'Resolved' or complaint.status == 'Closed':
            flash('This complaint is already resolved or closed.', 'warning')
            return redirect(url_for('complaint_detail', complaint_id=complaint_id))
        
        try:
            # Create live chat request
            live_chat_request = LiveChatRequest(
                complaint_id=complaint_id,
                user_id=current_user.id,
                status='Pending'
            )
            db.session.add(live_chat_request)
            
            # Update complaint
            complaint.is_escalated = True
            complaint.status = 'Escalated'
            complaint.escalation_time = datetime.utcnow()
            
            # Add system message
            system_message = ComplaintMessage(
                complaint_id=complaint_id,
                sender_id=current_user.id,
                message="🟢 LIVE CHAT REQUESTED: Customer has requested a live chat session. Admin has been notified.",
                is_admin_reply=False,
                is_system_message=True
            )
            db.session.add(system_message)
            
            db.session.commit()
            
            flash('Live chat request sent! Admin has been notified. You will be contacted shortly.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
        
        return redirect(url_for('complaint_detail', complaint_id=complaint_id))


    @app.route('/api/complaint/<int:complaint_id>/live-chat-status')
    @login_required
    def live_chat_status(complaint_id):
        """Check live chat request status"""
        from models import LiveChatRequest
        
        live_chat_request = LiveChatRequest.query.filter_by(
            complaint_id=complaint_id,
            user_id=current_user.id
        ).first()
        
        if live_chat_request:
            return jsonify({
                'success': True,
                'status': live_chat_request.status,
                'requested_at': live_chat_request.requested_at.strftime('%Y-%m-%d %H:%M') if live_chat_request.requested_at else None,
                'accepted_at': live_chat_request.accepted_at.strftime('%Y-%m-%d %H:%M') if live_chat_request.accepted_at else None
            })
        
        return jsonify({'success': False, 'status': 'No request found'})


    # ========================================================
    # ERROR HANDLERS
    # ========================================================

    @app.errorhandler(404)
    def page_not_found(error):

        return render_template(
            '404.html'
        ), 404


    @app.errorhandler(403)
    def forbidden(error):

        return render_template(
            '403.html'
        ), 403


    @app.errorhandler(500)
    def internal_server_error(error):

        db.session.rollback()

        return render_template(
            '500.html'
        ), 500


    return app


# ================================================================
# SAMPLE DATA
# ================================================================

def create_sample_data():
    """
    Create sample data for development.
    Runs only when database is empty.
    """

    from models import (
        User,
        Category,
        Product,
        Courier
    )

    # ------------------------------------------------------------
    # Check existing data
    # ------------------------------------------------------------

    if User.query.count() > 0:

        print(
            "📦 Sample data already exists. Skipping..."
        )

        return

    print(
        "📦 Creating sample data..."
    )

    # ============================================================
    # ADMIN USER
    # ============================================================

    admin = User(
        full_name='Admin User',
        email='admin@premiumstore.pk',
        phone='0300-1234567',
        role='admin',
        is_active=True
    )

    admin.set_password(
        'Admin@123'
    )

    db.session.add(
        admin
    )

    # ============================================================
    # REGULAR USER
    # ============================================================

    user = User(
        full_name='John Doe',
        email='john@example.com',
        phone='0300-7654321',
        role='customer',
        is_active=True
    )

    user.set_password(
        'John@123'
    )

    db.session.add(
        user
    )

    # ============================================================
    # CATEGORIES
    # ============================================================

    categories = [

        Category(
            name='Audio',
            slug='audio',
            description=(
                'Premium audio products including '
                'headphones, speakers, and earbuds'
            )
        ),

        Category(
            name='Smart Watches',
            slug='smart-watches',
            description=(
                'Advanced smart watches for everyday life'
            )
        ),

        Category(
            name='Mobile Accessories',
            slug='mobile-accessories',
            description=(
                'Protective cases, screen protectors, '
                'and more'
            )
        ),

        Category(
            name='Charging',
            slug='charging',
            description=(
                'Fast charging solutions and cables'
            )
        ),

        Category(
            name='Lifestyle',
            slug='lifestyle',
            description=(
                'Premium lifestyle and tech accessories'
            )
        )
    ]

    db.session.add_all(
        categories
    )

    db.session.flush()

    # ============================================================
    # PRODUCTS
    # ============================================================

    products = [

        Product(
            name='Premium Wireless Headphones Pro',
            slug='premium-wireless-headphones-pro',
            short_description=(
                'High-quality wireless headphones '
                'with noise cancellation'
            ),
            description=(
                'Experience premium sound quality with '
                'our flagship wireless headphones. '
                'Features active noise cancellation, '
                '40-hour battery life, and '
                'ultra-comfortable design.'
            ),
            price=4999,
            sale_price=2999,
            discount_percentage=40,
            category_id=categories[0].id,
            brand='PremiumAudio',
            stock_quantity=50,
            sku='PH-001',
            main_image=(
                'https://via.placeholder.com/'
                '300x300/2D1B69/ffffff?text=Headphones'
            ),
            rating=4.8,
            review_count=156,
            is_featured=True,
            is_bestseller=True,
            is_new=False,
            is_active=True
        ),

        Product(
            name='Smart Watch Series X',
            slug='smart-watch-series-x',
            short_description=(
                'Advanced smart watch with '
                'health tracking'
            ),
            description=(
                'The ultimate smart watch with heart '
                'rate monitoring, GPS, sleep tracking, '
                'and 14-day battery life.'
            ),
            price=8999,
            sale_price=5499,
            discount_percentage=39,
            category_id=categories[1].id,
            brand='PremiumTech',
            stock_quantity=30,
            sku='SW-001',
            main_image=(
                'https://via.placeholder.com/'
                '300x300/2D1B69/ffffff?text=Smart+Watch'
            ),
            rating=4.9,
            review_count=89,
            is_featured=True,
            is_bestseller=True,
            is_new=False,
            is_active=True
        ),

        Product(
            name='Premium Phone Case Ultra',
            slug='premium-phone-case-ultra',
            short_description=(
                'Military-grade protection for your phone'
            ),
            description=(
                'Ultra-durable phone case with shock '
                'absorption, raised edges, and a slim profile.'
            ),
            price=1299,
            sale_price=799,
            discount_percentage=38,
            category_id=categories[2].id,
            brand='PremiumCase',
            stock_quantity=100,
            sku='PC-001',
            main_image=(
                'https://via.placeholder.com/'
                '300x300/2D1B69/ffffff?text=Phone+Case'
            ),
            rating=4.6,
            review_count=67,
            is_featured=False,
            is_bestseller=True,
            is_new=False,
            is_active=True
        ),

        Product(
            name='USB-C Fast Charging Kit',
            slug='usb-c-fast-charging-kit',
            short_description=(
                '65W fast charging with multiple ports'
            ),
            description=(
                'Complete charging solution with 65W '
                'GaN technology. Includes 2 USB-C ports '
                'and 1 USB-A port.'
            ),
            price=2499,
            sale_price=1499,
            discount_percentage=40,
            category_id=categories[3].id,
            brand='PremiumCharge',
            stock_quantity=75,
            sku='CH-001',
            main_image=(
                'https://via.placeholder.com/'
                '300x300/2D1B69/ffffff?text=Charger'
            ),
            rating=4.7,
            review_count=45,
            is_featured=False,
            is_bestseller=False,
            is_new=True,
            is_active=True
        ),

        Product(
            name='Wireless Earbuds Mini',
            slug='wireless-earbuds-mini',
            short_description=(
                'Compact wireless earbuds with premium sound'
            ),
            description=(
                'Ultra-compact wireless earbuds with '
                'rich bass, clear treble, and 24-hour '
                'battery life.'
            ),
            price=3499,
            sale_price=1999,
            discount_percentage=43,
            category_id=categories[0].id,
            brand='PremiumAudio',
            stock_quantity=60,
            sku='EB-001',
            main_image=(
                'https://via.placeholder.com/'
                '300x300/2D1B69/ffffff?text=Earbuds'
            ),
            rating=4.5,
            review_count=123,
            is_featured=True,
            is_bestseller=False,
            is_new=True,
            is_active=True
        ),

        Product(
            name='Premium Leather Watch Band',
            slug='premium-leather-watch-band',
            short_description=(
                'Genuine leather band for smart watches'
            ),
            description=(
                'Genuine Italian leather watch band. '
                'Compatible with all standard smart watches.'
            ),
            price=1799,
            sale_price=None,
            discount_percentage=0,
            category_id=categories[4].id,
            brand='PremiumLifestyle',
            stock_quantity=40,
            sku='LB-001',
            main_image=(
                'https://via.placeholder.com/'
                '300x300/2D1B69/ffffff?text=Watch+Band'
            ),
            rating=4.3,
            review_count=34,
            is_featured=False,
            is_bestseller=False,
            is_new=True,
            is_active=True
        ),

        Product(
            name='Gaming Headset Pro',
            slug='gaming-headset-pro',
            short_description=(
                'Professional gaming headset '
                'with surround sound'
            ),
            description=(
                'Immerse yourself in gaming with 7.1 '
                'surround sound, noise-canceling microphone, '
                'and RGB lighting.'
            ),
            price=5999,
            sale_price=3999,
            discount_percentage=33,
            category_id=categories[0].id,
            brand='PremiumGaming',
            stock_quantity=25,
            sku='GH-001',
            main_image=(
                'https://via.placeholder.com/'
                '300x300/2D1B69/ffffff?text=Gaming+Headset'
            ),
            rating=4.8,
            review_count=78,
            is_featured=True,
            is_bestseller=False,
            is_new=True,
            is_active=True
        ),

        Product(
            name='Wireless Charging Pad',
            slug='wireless-charging-pad',
            short_description=(
                'Fast wireless charging for all devices'
            ),
            description=(
                'Premium wireless charging pad with '
                '15W fast charging. Compatible with '
                'iPhone, Samsung, and all Qi-enabled devices.'
            ),
            price=999,
            sale_price=699,
            discount_percentage=30,
            category_id=categories[3].id,
            brand='PremiumCharge',
            stock_quantity=80,
            sku='WC-001',
            main_image=(
                'https://via.placeholder.com/'
                '300x300/2D1B69/ffffff?text=Charging+Pad'
            ),
            rating=4.4,
            review_count=56,
            is_featured=False,
            is_bestseller=False,
            is_new=True,
            is_active=True
        ),

        Product(
            name='Premium Bluetooth Speaker',
            slug='premium-bluetooth-speaker',
            short_description=(
                'Portable Bluetooth speaker with 360° sound'
            ),
            description=(
                'Premium portable speaker with 20W output, '
                '20-hour battery life, and waterproof design.'
            ),
            price=3999,
            sale_price=2999,
            discount_percentage=25,
            category_id=categories[0].id,
            brand='PremiumAudio',
            stock_quantity=0,
            sku='SP-001',
            main_image=(
                'https://via.placeholder.com/'
                '300x300/2D1B69/ffffff?text=Speaker'
            ),
            rating=4.2,
            review_count=45,
            is_featured=False,
            is_bestseller=False,
            is_new=False,
            is_active=True
        )
    ]

    db.session.add_all(
        products
    )

    # ============================================================
    # COURIERS
    # ============================================================

    couriers = [

        Courier(
            name='TCS',
            website='https://tcs.com.pk',
            tracking_url_template=(
                'https://tcs.com.pk/tracking/{tracking_number}'
            )
        ),

        Courier(
            name='Leopards Courier',
            website='https://leopards.com.pk',
            tracking_url_template=(
                'https://leopards.com.pk/track/{tracking_number}'
            )
        ),

        Courier(
            name='M&P',
            website='https://mp.com.pk',
            tracking_url_template=(
                'https://mp.com.pk/tracking/{tracking_number}'
            )
        ),

        Courier(
            name='Trax',
            website='https://trax.com.pk',
            tracking_url_template=(
                'https://trax.com.pk/track/{tracking_number}'
            )
        ),

        Courier(
            name='PostEx',
            website='https://postex.com.pk',
            tracking_url_template=(
                'https://postex.com.pk/track/{tracking_number}'
            )
        ),

        Courier(
            name='Call Courier',
            website='https://callcourier.com.pk',
            tracking_url_template=(
                'https://callcourier.com.pk/tracking/'
                '{tracking_number}'
            )
        ),

        Courier(
            name='BlueEx',
            website='https://blueex.com.pk',
            tracking_url_template=(
                'https://blueex.com.pk/track/{tracking_number}'
            )
        ),

        Courier(
            name='Rider',
            website='https://rider.com.pk',
            tracking_url_template=(
                'https://rider.com.pk/tracking/{tracking_number}'
            )
        ),

        Courier(
            name='Other',
            website=None,
            tracking_url_template=None
        )
    ]

    db.session.add_all(
        couriers
    )

    # ============================================================
    # COMMIT
    # ============================================================

    db.session.commit()

    print(
        "✅ Sample data created successfully!"
    )

    print(
        "   👤 Admin: "
        "admin@premiumstore.pk / Admin@123"
    )

    print(
        "   👤 User: "
        "john@example.com / John@123"
    )

    print(
        "   📦 Products: 9 products added"
    )

    print(
        "   📂 Categories: 5 categories added"
    )

    print(
        "   📬 Couriers: 9 couriers added"
    )


# ================================================================
# CREATE APPLICATION
# ================================================================

app = create_app(
    os.getenv(
        'FLASK_ENV',
        'development'
    )
)


# ================================================================
# RUN APPLICATION
# ================================================================

if __name__ == '__main__':

    app.run(
        debug=True
    )