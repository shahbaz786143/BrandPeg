from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import db

# ==================== USER MODEL ====================
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='customer')  # customer, admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    orders = db.relationship('Order', back_populates='user', lazy=True)
    wishlist_items = db.relationship('Wishlist', back_populates='user', lazy=True)
    reviews = db.relationship('Review', back_populates='user', lazy=True)
    chat_conversations = db.relationship('ChatConversation', back_populates='user', lazy=True)
    complaints = db.relationship('Complaint', back_populates='user', lazy=True)
    
    def set_password(self, password):
        """Hash and set the password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if the password matches the hash"""
        return check_password_hash(self.password_hash, password)
    
    def get_total_orders(self):
        """Get total number of orders"""
        return len(self.orders)
    
    def get_total_spent(self):
        """Get total amount spent"""
        return sum(order.total_amount for order in self.orders if order.order_status == 'Delivered')
    
    def __repr__(self):
        return f'<User {self.email}>'


# ==================== CATEGORY MODEL ====================
class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', back_populates='category', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'


# ==================== PRODUCT MODEL ====================
class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    short_description = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    sale_price = db.Column(db.Float, nullable=True)
    discount_percentage = db.Column(db.Float, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    brand = db.Column(db.String(100), nullable=True)
    stock_quantity = db.Column(db.Integer, default=0)
    sku = db.Column(db.String(50), unique=True, nullable=True)
    main_image = db.Column(db.String(255), nullable=True)
    rating = db.Column(db.Float, default=0)
    review_count = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_bestseller = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = db.relationship('Category', back_populates='products')
    images = db.relationship('ProductImage', back_populates='product', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', back_populates='product', lazy=True)
    wishlist_items = db.relationship('Wishlist', back_populates='product', lazy=True)
    order_items = db.relationship('OrderItem', back_populates='product', lazy=True)
    
    def get_discounted_price(self):
        """Get the discounted price if sale price exists"""
        return self.sale_price if self.sale_price and self.sale_price < self.price else self.price
    
    def get_discount_percentage(self):
        """Calculate discount percentage"""
        if self.sale_price and self.sale_price < self.price:
            return round(((self.price - self.sale_price) / self.price) * 100)
        return 0
    
    def is_in_stock(self):
        """Check if product is in stock"""
        return self.stock_quantity > 0
    
    def get_stock_status(self):
        """Get stock status label"""
        if self.stock_quantity > 10:
            return 'In Stock'
        elif self.stock_quantity > 0:
            return 'Low Stock'
        else:
            return 'Out of Stock'
    
    def get_rating_stars(self):
        """Get rating as stars (1-5)"""
        return round(self.rating) if self.rating else 0
    
    def __repr__(self):
        return f'<Product {self.name}>'


# ==================== PRODUCT IMAGE MODEL ====================
class ProductImage(db.Model):
    __tablename__ = 'product_images'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    is_main = db.Column(db.Boolean, default=False)
    alt_text = db.Column(db.String(200), nullable=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product', back_populates='images')
    
    def __repr__(self):
        return f'<ProductImage {self.id}>'


# ==================== ORDER MODEL ====================
class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Nullable for guest orders
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(100), nullable=False)
    postal_code = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    subtotal = db.Column(db.Float, nullable=False)
    shipping_fee = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # COD, etc.
    order_status = db.Column(db.String(50), default='Pending')  # Pending, Confirmed, Processing, Shipped, Out for Delivery, Delivered, Cancelled, Returned
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', lazy=True, cascade='all, delete-orphan')
    shipment = db.relationship('Shipment', back_populates='order', uselist=False, lazy=True)
    
    def get_status_badge_color(self):
        """Get Bootstrap badge color for status"""
        colors = {
            'Pending': 'warning',
            'Confirmed': 'info',
            'Processing': 'primary',
            'Shipped': 'info',
            'Out for Delivery': 'warning',
            'Delivered': 'success',
            'Cancelled': 'danger',
            'Returned': 'secondary'
        }
        return colors.get(self.order_status, 'secondary')
    
    def get_status_icon(self):
        """Get icon for status"""
        icons = {
            'Pending': 'fa-clock',
            'Confirmed': 'fa-check-circle',
            'Processing': 'fa-spinner',
            'Shipped': 'fa-truck',
            'Out for Delivery': 'fa-truck-fast',
            'Delivered': 'fa-check-double',
            'Cancelled': 'fa-times-circle',
            'Returned': 'fa-undo'
        }
        return icons.get(self.order_status, 'fa-circle')
    
    def __repr__(self):
        return f'<Order {self.order_number}>'


# ==================== ORDER ITEM MODEL ====================
class OrderItem(db.Model):
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)  # Price at time of order
    subtotal = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    order = db.relationship('Order', back_populates='items')
    product = db.relationship('Product', back_populates='order_items')
    
    def __repr__(self):
        return f'<OrderItem {self.id}>'


# ==================== WISHLIST MODEL ====================
class Wishlist(db.Model):
    __tablename__ = 'wishlist'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='wishlist_items')
    product = db.relationship('Product', back_populates='wishlist_items')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='unique_wishlist'),)
    
    def __repr__(self):
        return f'<Wishlist {self.user_id}-{self.product_id}>'


# ==================== REVIEW MODEL (UPDATED) ====================
class Review(db.Model):
    __tablename__ = 'reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text, nullable=True)
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='reviews')
    product = db.relationship('Product', back_populates='reviews')
    images = db.relationship('ReviewImage', back_populates='review', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='unique_review'),)
    
    def __repr__(self):
        return f'<Review {self.id}>'


# ==================== REVIEW IMAGE MODEL ====================
class ReviewImage(db.Model):
    __tablename__ = 'review_images'
    
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    review = db.relationship('Review', back_populates='images')
    
    def __repr__(self):
        return f'<ReviewImage {self.id}>'


# ==================== COURIER MODEL ====================
class Courier(db.Model):
    __tablename__ = 'couriers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    website = db.Column(db.String(255), nullable=True)
    tracking_url_template = db.Column(db.String(255), nullable=True)  # e.g., https://tcs.com/track/{tracking_number}
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shipments = db.relationship('Shipment', back_populates='courier', lazy=True)
    
    def get_tracking_url(self, tracking_number):
        """Generate tracking URL using template"""
        if self.tracking_url_template and tracking_number:
            return self.tracking_url_template.replace('{tracking_number}', tracking_number)
        return None
    
    def __repr__(self):
        return f'<Courier {self.name}>'


# ==================== SHIPMENT MODEL ====================
class Shipment(db.Model):
    __tablename__ = 'shipments'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), unique=True, nullable=False)
    courier_id = db.Column(db.Integer, db.ForeignKey('couriers.id'), nullable=True)
    tracking_number = db.Column(db.String(100), nullable=True)
    tracking_url = db.Column(db.String(255), nullable=True)
    shipment_date = db.Column(db.DateTime, nullable=True)
    delivery_date = db.Column(db.DateTime, nullable=True)
    shipping_status = db.Column(db.String(50), default='Pending')  # Pending, In Transit, Delivered, Failed
    admin_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order = db.relationship('Order', back_populates='shipment')
    courier = db.relationship('Courier', back_populates='shipments')
    
    def get_status_badge_color(self):
        """Get Bootstrap badge color for shipping status"""
        colors = {
            'Pending': 'secondary',
            'In Transit': 'info',
            'Delivered': 'success',
            'Failed': 'danger'
        }
        return colors.get(self.shipping_status, 'secondary')
    
    def __repr__(self):
        return f'<Shipment {self.id}>'


# ==================== CART MODEL ====================
class Cart(db.Model):
    __tablename__ = 'carts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Nullable for guest users
    session_id = db.Column(db.String(100), nullable=True)  # For guest users
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', lazy=True)
    product = db.relationship('Product', lazy=True)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='unique_cart_user_product'),)
    
    def __repr__(self):
        return f'<Cart {self.id}>'


# ==================== CHAT / HELP DESK MODELS ====================

class ChatConversation(db.Model):
    __tablename__ = 'chat_conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), default='Open')  # Open, In Progress, Resolved, Closed
    priority = db.Column(db.String(20), default='Normal')  # Low, Normal, High, Urgent
    category = db.Column(db.String(50), nullable=True)  # Order Issue, Product Question, Complaint, Other
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='chat_conversations')
    messages = db.relationship('ChatMessage', back_populates='conversation', lazy=True, cascade='all, delete-orphan')
    order = db.relationship('Order', lazy=True)
    
    def __repr__(self):
        return f'<ChatConversation {self.id}>'
    
    def get_last_message(self):
        """Get the last message in this conversation"""
        if self.messages:
            return self.messages[-1]
        return None
    
    def get_unread_count(self, user_id=None):
        """Get count of unread messages"""
        if user_id:
            return ChatMessage.query.filter_by(
                conversation_id=self.id,
                is_read=False
            ).filter(ChatMessage.sender_id != user_id).count()
        return ChatMessage.query.filter_by(
            conversation_id=self.id,
            is_read=False
        ).count()


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('chat_conversations.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    is_admin_reply = db.Column(db.Boolean, default=False)
    is_system_message = db.Column(db.Boolean, default=False)  # NEW FIELD ADDED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    conversation = db.relationship('ChatConversation', back_populates='messages')
    sender = db.relationship('User', lazy=True)
    
    def __repr__(self):
        return f'<ChatMessage {self.id}>'


# ==================== COMPLAINT / TICKET MODELS ====================

class Complaint(db.Model):
    __tablename__ = 'complaints'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    order_number = db.Column(db.String(50), nullable=True)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='General')
    priority = db.Column(db.String(20), default='Normal')
    status = db.Column(db.String(50), default='Pending')
    is_escalated = db.Column(db.Boolean, default=False)
    escalation_time = db.Column(db.DateTime, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    resolution = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='complaints')
    order = db.relationship('Order', lazy=True)
    messages = db.relationship('ComplaintMessage', back_populates='complaint', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Complaint {self.id}>'
    
    def get_time_elapsed(self):
        """Get time elapsed since complaint was created"""
        if self.created_at:
            now = datetime.utcnow()
            delta = now - self.created_at
            return delta
        return None
    
    def is_24_hours_passed(self):
        """Check if 24 hours have passed since complaint creation"""
        if self.created_at:
            now = datetime.utcnow()
            delta = now - self.created_at
            return delta.total_seconds() >= 86400  # 24 hours in seconds
        return False
    
    def can_escalate(self):
        """Check if complaint can be escalated to live chat"""
        return self.is_24_hours_passed() and self.status not in ['Resolved', 'Closed']


class ComplaintMessage(db.Model):
    __tablename__ = 'complaint_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_admin_reply = db.Column(db.Boolean, default=False)
    is_system_message = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    complaint = db.relationship('Complaint', back_populates='messages')
    sender = db.relationship('User', lazy=True)
    
    def __repr__(self):
        return f'<ComplaintMessage {self.id}>'


class LiveChatRequest(db.Model):
    __tablename__ = 'live_chat_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(50), default='Pending')  # Pending, Accepted, Rejected, Completed
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    accepted_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationships
    complaint = db.relationship('Complaint', lazy=True)
    user = db.relationship('User', foreign_keys=[user_id], lazy=True)
    admin = db.relationship('User', foreign_keys=[admin_id], lazy=True)
    
    def __repr__(self):
        return f'<LiveChatRequest {self.id}>'