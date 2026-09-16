from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime
import re

from models import User
from database import db

auth_bp = Blueprint('auth', __name__)

# ==================== HELPER FUNCTIONS ====================

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate Pakistani phone number"""
    pattern = r'^03[0-9]{9}$'
    return re.match(pattern, phone) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, 'Password must be at least 8 characters long.'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter.'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter.'
    if not re.search(r'[0-9]', password):
        return False, 'Password must contain at least one number.'
    return True, ''

# ==================== ROUTES ====================

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        terms = request.form.get('terms')
        
        # Validate inputs
        if not full_name:
            flash('Please enter your full name.', 'danger')
            return render_template('register.html')
        
        if not validate_email(email):
            flash('Please enter a valid email address.', 'danger')
            return render_template('register.html')
        
        if not validate_phone(phone):
            flash('Please enter a valid Pakistani phone number (03XX-XXXXXXX).', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        
        is_valid, error_msg = validate_password(password)
        if not is_valid:
            flash(error_msg, 'danger')
            return render_template('register.html')
        
        if not terms:
            flash('You must agree to the Terms of Service.', 'danger')
            return render_template('register.html')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('This email is already registered. Please login instead.', 'danger')
            return render_template('register.html')
        
        # Create new user
        try:
            user = User(
                full_name=full_name,
                email=email,
                phone=phone,
                role='customer',
                is_active=True
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            flash('Your account has been created successfully! Please login.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'danger')
            return render_template('register.html')
    
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        # Redirect admin to admin dashboard
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html')
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')
        
        if not user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'danger')
            return render_template('login.html')
        
        # Check password
        if not user.check_password(password):
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')
        
        # Login user
        login_user(user, remember=remember)
        
        # Update last login
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Redirect based on role
        if user.role == 'admin':
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            flash(f'Welcome back, Admin {user.full_name}!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('index'))
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))

@auth_bp.route('/account')
@login_required
def account():
    """User account page"""
    return render_template('account.html', user=current_user)

@auth_bp.route('/account/update', methods=['POST'])
@login_required
def update_account():
    """Update user account"""
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    user = current_user
    
    # Update name
    if full_name:
        user.full_name = full_name
    
    # Update phone
    if phone:
        if not validate_phone(phone):
            flash('Please enter a valid Pakistani phone number.', 'danger')
            return redirect(url_for('auth.account'))
        user.phone = phone
    
    # Update password
    if current_password or new_password or confirm_password:
        if not user.check_password(current_password):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('auth.account'))
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('auth.account'))
        
        is_valid, error_msg = validate_password(new_password)
        if not is_valid:
            flash(error_msg, 'danger')
            return redirect(url_for('auth.account'))
        
        user.set_password(new_password)
    
    user.updated_at = datetime.utcnow()
    db.session.commit()
    
    flash('Your account has been updated successfully!', 'success')
    return redirect(url_for('auth.account'))

@auth_bp.route('/auth/check-email')
def check_email():
    """Check if email is available (AJAX)"""
    email = request.args.get('email', '').strip().lower()
    if not email:
        return {'available': False}
    
    user = User.query.filter_by(email=email).first()
    return {'available': user is None}