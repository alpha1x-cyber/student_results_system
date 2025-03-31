import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort
from flask_mysqldb import MySQL
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from PIL import Image
import uuid

# تهيئة التطبيق
app = Flask(__name__)
app.config.from_object(Config)

# تهيئة قاعدة البيانات MySQL
mysql = MySQL(app)

# تهيئة Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'admin_login'

# نموذج المستخدم
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

# مستخدمين النظام (يمكن تخزينهم في قاعدة بيانات)
users = {
    1: User(1, 'admin', generate_password_hash('admin123'))
}

@login_manager.user_loader
def load_user(user_id):
    return users.get(int(user_id))

# وظيفة للتحقق من امتدادات الملفات المسموح بها
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# إنشاء مجلد التحميل إذا لم يكن موجودًا
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# إنشاء جدول النتائج إذا لم يكن موجودًا
with app.app_context():
    cur = mysql.connection.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INT AUTO_INCREMENT PRIMARY KEY,
            exam_number VARCHAR(50) UNIQUE NOT NULL,
            filename VARCHAR(255) NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    mysql.connection.commit()
    cur.close()

# الصفحة الرئيسية
@app.route('/')
def index():
    return render_template('index.html')

# صفحة البحث عن النتيجة
@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        exam_number = request.form.get('exam_number')
        
        if not exam_number:
            flash('يرجى إدخال رقم الامتحان', 'error')
            return redirect(url_for('search'))
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT filename FROM results WHERE exam_number = %s", (exam_number,))
        result = cur.fetchone()
        cur.close()
        
        if result:
            filename = result[0]
            return redirect(url_for('show_result', exam_number=exam_number))
        else:
            flash('لا توجد نتيجة لهذا الرقم', 'error')
    
    return render_template('search.html')

# عرض النتيجة
@app.route('/result/<exam_number>')
def show_result(exam_number):
    cur = mysql.connection.cursor()
    cur.execute("SELECT filename FROM results WHERE exam_number = %s", (exam_number,))
    result = cur.fetchone()
    cur.close()
    
    if not result:
        abort(404)
    
    filename = result[0]
    return render_template('result.html', exam_number=exam_number, filename=filename)

# تحميل النتيجة
@app.route('/download/<filename>')
def download_result(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)

# لوحة التحكم - تسجيل الدخول
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = None
        for u in users.values():
            if u.username == username:
                user = u
                break
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    
    return render_template('admin/login.html')

# لوحة التحكم - الرئيسية
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT exam_number, filename, uploaded_at FROM results ORDER BY uploaded_at DESC")
    results = cur.fetchall()
    cur.close()
    
    return render_template('admin/dashboard.html', results=results)

# لوحة التحكم - رفع النتائج
@app.route('/admin/upload', methods=['POST'])
@login_required
def admin_upload():
    if 'file' not in request.files:
        flash('لم يتم اختيار ملف', 'error')
        return redirect(url_for('admin_dashboard'))
    
    file = request.files['file']
    exam_number = request.form.get('exam_number')
    
    if not exam_number:
        flash('يرجى إدخال رقم الامتحان', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if file.filename == '':
        flash('لم يتم اختيار ملف', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if file and allowed_file(file.filename):
        # إنشاء اسم فريد للملف
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{exam_number}.{ext}"
        filename = secure_filename(unique_filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # حفظ الملف
        file.save(filepath)
        
        # إذا كان الملف صورة، يمكن تحسينها
        if ext in ['png', 'jpg', 'jpeg']:
            img = Image.open(filepath)
            img.save(filepath, optimize=True, quality=85)
        
        # حفظ المعلومات في قاعدة البيانات
        try:
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO results (exam_number, filename) VALUES (%s, %s)",
                (exam_number, filename)
            )
            mysql.connection.commit()
            cur.close()
            
            flash('تم رفع النتيجة بنجاح', 'success')
        except Exception as e:
            # إذا كان هناك خطأ، احذف الملف المحمل
            if os.path.exists(filepath):
                os.remove(filepath)
            
            flash('خطأ في رفع النتيجة. قد يكون رقم الامتحان مكررًا', 'error')
    else:
        flash('نوع الملف غير مسموح به', 'error')
    
    return redirect(url_for('admin_dashboard'))

# لوحة التحكم - حذف النتيجة
@app.route('/admin/delete/<exam_number>')
@login_required
def admin_delete(exam_number):
    cur = mysql.connection.cursor()
    
    # الحصول على اسم الملف
    cur.execute("SELECT filename FROM results WHERE exam_number = %s", (exam_number,))
    result = cur.fetchone()
    
    if result:
        filename = result[0]
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # حذف الملف إذا كان موجودًا
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # حذف السجل من قاعدة البيانات
        cur.execute("DELETE FROM results WHERE exam_number = %s", (exam_number,))
        mysql.connection.commit()
        flash('تم حذف النتيجة بنجاح', 'success')
    else:
        flash('لم يتم العثور على النتيجة', 'error')
    
    cur.close()
    return redirect(url_for('admin_dashboard'))

# لوحة التحكم - تسجيل الخروج
@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))

# معالج الأخطاء 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)