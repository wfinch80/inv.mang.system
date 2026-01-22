import os
from functools import wraps
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# --- SETUP ---
basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')

app = Flask(__name__)
db_path = os.path.join(basedir, "inventory.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'secret-key-replace-me'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
db = SQLAlchemy(app)

# --- MODELS ---
class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    barcode = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(100))
    quantity = db.Column(db.Integer, default=0)
    low_stock_threshold = db.Column(db.Integer, default=10)
    image_filename = db.Column(db.String(200))
    reorder_url = db.Column(db.String(500))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'barcode': self.barcode,
            'quantity': self.quantity,
            'low_stock_threshold': self.low_stock_threshold,
            'category': self.category,
            'reorder_url': self.reorder_url,
            'image_url': url_for('uploaded_file', filename=self.image_filename) if self.image_filename else None
        }

class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class UsageLog(db.Model):
    __tablename__ = 'usage_log'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    quantity_used = db.Column(db.Integer, default=1)
    apartment_number = db.Column(db.String(20))
    employee_number = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    item = db.relationship('Item', backref='usage_logs')

class ToolTracking(db.Model):
    __tablename__ = 'tool_tracking'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    employee_name = db.Column(db.String(100))
    action = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    item = db.relationship('Item', backref='tool_tracking')
    def to_dict(self):
        return {
            'id': self.id,
            'item_name': self.item.name,
            'employee_name': self.employee_name,
            'action': self.action,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M')
        }

# --- HELPERS ---
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'): return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---
@app.route('/')
def landing(): return render_template('landing.html')

@app.route('/scanner')
def scanner(): return render_template('scanner.html')

@app.route('/admin')
@require_admin
def admin(): return render_template('admin.html')

@app.route('/history')
@require_admin
def history():
    logs = UsageLog.query.order_by(UsageLog.timestamp.desc()).limit(100).all()
    return render_template('history.html', logs=logs)

@app.route('/admin/users')
@require_admin
def manage_users():
    users = AdminUser.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/change-password', methods=['GET', 'POST'])
@require_admin
def change_password():
    if request.method == 'POST':
        user = AdminUser.query.get(session.get('admin_id'))
        if user:
            user.set_password(request.form.get('password'))
            db.session.commit()
            return redirect(url_for('admin'))
    return render_template('change_password.html')

# --- API ENDPOINTS ---

@app.route('/api/items', methods=['GET'])
def get_items():
    items = Item.query.all()
    return jsonify([i.to_dict() for i in items])

@app.route('/api/low_stock_alerts', methods=['GET'])
def low_stock_alerts():
    low_items = Item.query.filter(Item.quantity <= Item.low_stock_threshold).all()
    return jsonify([i.to_dict() for i in low_items])

@app.route('/api/item/<barcode>', methods=['GET'])
def get_item(barcode):
    item = Item.query.filter_by(barcode=barcode).first()
    if item: return jsonify(item.to_dict())
    return jsonify({'error': 'Not found'}), 404

# ADD ITEM
@app.route('/api/item', methods=['POST'])
@require_admin
def add_item_api():
    try:
        if Item.query.filter_by(barcode=request.form['barcode']).first():
            return jsonify({'error': 'Barcode exists'}), 400

        filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                filename = secure_filename(f"{request.form['barcode']}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_item = Item(
            name=request.form['name'],
            barcode=request.form['barcode'],
            quantity=int(request.form['quantity']),
            low_stock_threshold=int(request.form.get('low_stock_threshold', 10)),
            category=request.form.get('category'),
            image_filename=filename,
            reorder_url=request.form.get('reorder_url')
        )
        db.session.add(new_item)
        db.session.commit()
        return jsonify({'message': 'Success'})
    except Exception as e: return jsonify({'error': str(e)}), 500

# UPDATE ITEM (FIXES "SAVE" BUTTON)
@app.route('/api/update_item', methods=['POST'])
@require_admin
def update_item():
    try:
        item = Item.query.get(request.form.get('item_id'))
        if not item: return jsonify({'error': 'Item not found'}), 404

        item.name = request.form.get('name')
        item.barcode = request.form.get('barcode')
        item.category = request.form.get('category')
        item.quantity = int(request.form.get('quantity'))
        item.low_stock_threshold = int(request.form.get('low_stock_threshold'))
        item.reorder_url = request.form.get('reorder_url')

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(f"{item.barcode}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                item.image_filename = filename

        db.session.commit()
        return jsonify({'message': 'Success'})
    except Exception as e: return jsonify({'error': str(e)}), 500

# LOG TOOL (FIXES "TOOL" SCAN)
@app.route('/api/tool_tracking', methods=['GET', 'POST'])
def tool_tracking():
    if request.method == 'POST':
        data = request.json
        item = Item.query.filter_by(barcode=data.get('barcode')).first()
        if not item: return jsonify({'error': 'Item not found'}), 404

        log = ToolTracking(
            item_id=item.id,
            employee_name=data.get('employee_name'),
            action=data.get('action')
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({'message': 'Logged'})

    logs = ToolTracking.query.order_by(ToolTracking.timestamp.desc()).limit(50).all()
    return jsonify([l.to_dict() for l in logs])

@app.route('/api/log_usage', methods=['POST'])
def log_usage():
    data = request.json
    item = Item.query.filter_by(barcode=data.get('barcode')).first()
    if not item: return jsonify({'error': 'Not found'}), 404

    qty = int(data.get('quantity', 1))
    item.quantity -= qty
    log = UsageLog(item_id=item.id, quantity_used=qty)
    db.session.add(log)
    db.session.commit()
    return jsonify({'new_quantity': item.quantity})

# ADD USER (FIXES "ADD ADMIN")
@app.route('/admin/add_user', methods=['POST'])
@require_admin
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    if not AdminUser.query.filter_by(username=username).first():
        new_user = AdminUser(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
    return redirect(url_for('manage_users'))

@app.route('/admin/delete_user/<int:id>')
@require_admin
def delete_user(id):
    if id != session.get('admin_id'):
        user = AdminUser.query.get(id)
        if user:
            db.session.delete(user)
            db.session.commit()
    return redirect(url_for('manage_users'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = AdminUser.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            session['admin_logged_in'] = True
            session['admin_id'] = user.id
            return redirect(url_for('admin'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    db.create_all()
    if request.method == 'POST':
        if not AdminUser.query.first():
            admin = AdminUser(username=request.form['username'])
            admin.set_password(request.form['password'])
            db.session.add(admin)
            db.session.commit()
        return redirect(url_for('login'))
    return render_template('setup.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run()
