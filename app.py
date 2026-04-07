
app_py = '''"""
Ташкентский институт текстильной и лёгкой промышленности
Портал для русскоязычных студентов
"""

from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

# Инициализация приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = 'tashkent-textile-secret-key-2024'  # Ключ для сессий
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database/database.db'  # Путь к БД
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER_FILES'] = 'uploads/files'  # Папка для конспектов
app.config['UPLOAD_FOLDER_IMAGES'] = 'uploads/images'  # Папка для галереи
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Макс. размер файла 16MB

# Разрешённые расширения файлов
ALLOWED_EXTENSIONS_FILES = {'pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg'}
ALLOWED_EXTENSIONS_IMAGES = {'png', 'jpg', 'jpeg', 'gif'}

# Инициализация расширений
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Куда редиректить если не авторизован
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'

# ==================== МОДЕЛИ БАЗЫ ДАННЫХ ====================

class User(UserMixin, db.Model):
    """Модель пользователя"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # Роль администратора
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Schedule(db.Model):
    """Модель расписания занятий"""
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(50), nullable=False)  # Название группы
    day_of_week = db.Column(db.String(20), nullable=False)  # День недели
    subject = db.Column(db.String(100), nullable=False)  # Предмет
    teacher = db.Column(db.String(100))  # Преподаватель
    room = db.Column(db.String(20))  # Аудитория
    time_start = db.Column(db.String(10), nullable=False)  # Время начала
    time_end = db.Column(db.String(10), nullable=False)  # Время окончания
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class File(db.Model):
    """Модель файлов (конспекты)"""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)  # Имя файла на сервере
    original_name = db.Column(db.String(200), nullable=False)  # Оригинальное имя
    course = db.Column(db.String(50), nullable=False)  # Курс
    subject = db.Column(db.String(100), nullable=False)  # Предмет
    description = db.Column(db.Text)  # Описание
    file_type = db.Column(db.String(10))  # Тип файла (pdf, docx и т.д.)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    download_count = db.Column(db.Integer, default=0)  # Счётчик скачиваний

class Announcement(db.Model):
    """Модель объявлений"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)  # Заголовок
    content = db.Column(db.Text, nullable=False)  # Содержание
    category = db.Column(db.String(50), nullable=False)  # Категория (продам, куплю и т.д.)
    contact_info = db.Column(db.String(200))  # Контакты
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class News(db.Model):
    """Модель новостей"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(200))  # Картинка к новости (опционально)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)

class Gallery(db.Model):
    """Модель галереи"""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(200))  # Подпись к фото
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def allowed_file(filename, allowed_extensions):
    """Проверка разрешённого расширения файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя для Flask-Login"""
    return User.query.get(int(user_id))

def admin_required(f):
    """Декоратор для проверки прав администратора"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # Доступ запрещён
        return f(*args, **kwargs)
    return decorated_function

# ==================== МАРШРУТЫ ====================

@app.route('/')
def index():
    """Главная страница"""
    latest_news = News.query.order_by(News.created_at.desc()).limit(3).all()
    latest_announcements = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc()).limit(5).all()
    return render_template('index.html', news=latest_news, announcements=latest_announcements)

# ----- АУТЕНТИФИКАЦИЯ -----

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация пользователя"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Валидация
        if not all([username, email, password]):
            flash('Все поля обязательны для заполнения', 'danger')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Пароли не совпадают', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'danger')
            return redirect(url_for('register'))
        
        # Создание пользователя
        user = User(username=username, email=email)
        user.set_password(password)
        
        # Первый пользователь становится админом
        if User.query.count() == 0:
            user.is_admin = True
        
        db.session.add(user)
        db.session.commit()
        
        flash('Регистрация успешна! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Вход в систему"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'Добро пожаловать, {user.username}!', 'success')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы успешно вышли из системы', 'info')
    return redirect(url_for('index'))

# ----- РАСПИСАНИЕ -----

@app.route('/schedule')
def schedule():
    """Просмотр расписания"""
    groups = db.session.query(Schedule.group_name).distinct().all()
    groups = [g[0] for g in groups]
    
    selected_group = request.args.get('group', groups[0] if groups else None)
    
    schedule_data = {}
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
    
    if selected_group:
        for day in days:
            schedule_data[day] = Schedule.query.filter_by(
                group_name=selected_group, 
                day_of_week=day
            ).order_by(Schedule.time_start).all()
    
    return render_template('schedule.html', 
                         groups=groups, 
                         selected_group=selected_group, 
                         schedule_data=schedule_data,
                         days=days)

@app.route('/schedule/add', methods=['POST'])
@login_required
def add_schedule():
    """Добавление расписания (только админ)"""
    if not current_user.is_admin:
        abort(403)
    
    schedule_item = Schedule(
        group_name=request.form.get('group_name'),
        day_of_week=request.form.get('day_of_week'),
        subject=request.form.get('subject'),
        teacher=request.form.get('teacher'),
        room=request.form.get('room'),
        time_start=request.form.get('time_start'),
        time_end=request.form.get('time_end'),
        created_by=current_user.id
    )
    
    db.session.add(schedule_item)
    db.session.commit()
    flash('Расписание добавлено', 'success')
    return redirect(url_for('schedule', group=schedule_item.group_name))

@app.route('/schedule/delete/<int:id>')
@login_required
@admin_required
def delete_schedule(id):
    """Удаление расписания"""
    item = Schedule.query.get_or_404(id)
    group = item.group_name
    db.session.delete(item)
    db.session.commit()
    flash('Расписание удалено', 'success')
    return redirect(url_for('schedule', group=group))

# ----- ФАЙЛЫ И КОНСПЕКТЫ -----

@app.route('/files')
def files():
    """Раздел конспектов"""
    course = request.args.get('course', '')
    subject = request.args.get('subject', '')
    
    query = File.query
    if course:
        query = query.filter_by(course=course)
    if subject:
        query = query.filter(File.subject.contains(subject))
    
    files = query.order_by(File.uploaded_at.desc()).all()
    
    # Получаем уникальные курсы и предметы для фильтров
    courses = db.session.query(File.course).distinct().all()
    subjects = db.session.query(File.subject).distinct().all()
    
    return render_template('files.html', 
                         files=files, 
                         courses=courses, 
                         subjects=subjects,
                         selected_course=course,
                         selected_subject=subject)

@app.route('/files/upload', methods=['POST'])
@login_required
def upload_file():
    """Загрузка файла"""
    if 'file' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(url_for('files'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(url_for('files'))
    
    if file and allowed_file(file.filename, ALLOWED_EXTENSIONS_FILES):
        filename = secure_filename(file.filename)
        # Добавляем timestamp к имени файла для уникальности
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER_FILES'], filename)
        file.save(filepath)
        
        # Сохраняем в БД
        new_file = File(
            filename=filename,
            original_name=file.filename,
            course=request.form.get('course'),
            subject=request.form.get('subject'),
            description=request.form.get('description'),
            file_type=filename.rsplit('.', 1)[1].lower(),
            uploaded_by=current_user.id
        )
        
        db.session.add(new_file)
        db.session.commit()
        
        flash('Файл успешно загружен', 'success')
    else:
        flash('Недопустимый формат файла. Разрешены: PDF, DOCX, PNG', 'danger')
    
    return redirect(url_for('files'))

@app.route('/files/download/<int:id>')
def download_file(id):
    """Скачивание файла"""
    file_record = File.query.get_or_404(id)
    file_record.download_count += 1
    db.session.commit()
    
    return send_from_directory(
        app.config['UPLOAD_FOLDER_FILES'], 
        file_record.filename, 
        as_attachment=True,
        download_name=file_record.original_name
    )

@app.route('/files/delete/<int:id>')
@login_required
@admin_required
def delete_file(id):
    """Удаление файла"""
    file_record = File.query.get_or_404(id)
    
    # Удаляем физический файл
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER_FILES'], file_record.filename))
    except:
        pass
    
    db.session.delete(file_record)
    db.session.commit()
    flash('Файл удалён', 'success')
    return redirect(url_for('files'))

# ----- ОБЪЯВЛЕНИЯ -----

@app.route('/announcements')
def announcements():
    """Раздел объявлений"""
    category = request.args.get('category', '')
    
    query = Announcement.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    
    announcements = query.order_by(Announcement.created_at.desc()).all()
    categories = ['Продам', 'Куплю', 'Ищу напарника', 'Подработка', 'Другое']
    
    return render_template('announcements.html', 
                         announcements=announcements,
                         categories=categories,
                         selected_category=category)

@app.route('/announcements/add', methods=['POST'])
@login_required
def add_announcement():
    """Добавление объявления"""
    announcement = Announcement(
        title=request.form.get('title'),
        content=request.form.get('content'),
        category=request.form.get('category'),
        contact_info=request.form.get('contact_info'),
        user_id=current_user.id
    )
    
    db.session.add(announcement)
    db.session.commit()
    flash('Объявление добавлено', 'success')
    return redirect(url_for('announcements'))

@app.route('/announcements/delete/<int:id>')
@login_required
@admin_required
def delete_announcement(id):
    """Удаление объявления"""
    announcement = Announcement.query.get_or_404(id)
    db.session.delete(announcement)
    db.session.commit()
    flash('Объявление удалено', 'success')
    return redirect(url_for('announcements'))

# ----- НОВОСТИ -----

@app.route('/news')
def news_list():
    """Все новости"""
    news = News.query.order_by(News.created_at.desc()).all()
    return render_template('news.html', news=news)

@app.route('/news/<int:id>')
def news_detail(id):
    """Детальная страница новости"""
    item = News.query.get_or_404(id)
    item.views += 1
    db.session.commit()
    return render_template('news_detail.html', news=item)

@app.route('/news/add', methods=['POST'])
@login_required
@admin_required
def add_news():
    """Добавление новости"""
    news = News(
        title=request.form.get('title'),
        content=request.form.get('content'),
        author_id=current_user.id
    )
    
    db.session.add(news)
    db.session.commit()
    flash('Новость добавлена', 'success')
    return redirect(url_for('news_list'))

@app.route('/news/delete/<int:id>')
@login_required
@admin_required
def delete_news(id):
    """Удаление новости"""
    news = News.query.get_or_404(id)
    db.session.delete(news)
    db.session.commit()
    flash('Новость удалена', 'success')
    return redirect(url_for('news_list'))

# ----- ГАЛЕРЕЯ -----

@app.route('/gallery')
def gallery():
    """Галерея фотографий"""
    images = Gallery.query.order_by(Gallery.uploaded_at.desc()).all()
    return render_template('gallery.html', images=images)

@app.route('/gallery/upload', methods=['POST'])
@login_required
def upload_image():
    """Загрузка изображения"""
    if 'image' not in request.files:
        flash('Изображение не выбрано', 'danger')
        return redirect(url_for('gallery'))
    
    image = request.files['image']
    if image.filename == '':
        flash('Изображение не выбрано', 'danger')
        return redirect(url_for('gallery'))
    
    if image and allowed_file(image.filename, ALLOWED_EXTENSIONS_IMAGES):
        filename = secure_filename(image.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER_IMAGES'], filename)
        image.save(filepath)
        
        # Оптимизация изображения (опционально)
        try:
            from PIL import Image
            with Image.open(filepath) as img:
                img.thumbnail((1200, 1200))  # Максимальный размер
                img.save(filepath, optimize=True, quality=85)
        except:
            pass
        
        gallery_item = Gallery(
            filename=filename,
            caption=request.form.get('caption'),
            uploaded_by=current_user.id
        )
        
        db.session.add(gallery_item)
        db.session.commit()
        flash('Изображение добавлено', 'success')
    else:
        flash('Недопустимый формат. Разрешены: PNG, JPG, JPEG, GIF', 'danger')
    
    return redirect(url_for('gallery'))

@app.route('/gallery/delete/<int:id>')
@login_required
@admin_required
def delete_image(id):
    """Удаление изображения"""
    image = Gallery.query.get_or_404(id)
    
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER_IMAGES'], image.filename))
    except:
        pass
    
    db.session.delete(image)
    db.session.commit()
    flash('Изображение удалено', 'success')
    return redirect(url_for('gallery'))

# ----- АДМИН-ПАНЕЛЬ -----

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    """Административная панель"""
    stats = {
        'users': User.query.count(),
        'files': File.query.count(),
        'announcements': Announcement.query.count(),
        'news': News.query.count()
    }
    return render_template('admin.html', stats=stats)

# ----- КОНТЕКСТНЫЕ ПРОЦЕССОРЫ -----

@app.context_processor
def inject_globals():
    """Глобальные переменные для всех шаблонов"""
    return {
        'current_year': datetime.now().year,
        'site_name': 'ТашТЛИ - Студенческий портал'
    }

# ----- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ -----

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Создаём таблицы если их нет
        print("База данных инициализирована")
    
    # Для локальной разработки
    app.run(debug=True, host='0.0.0.0', port=5000)
'''

with open(f"{project_name}/app.py", "w", encoding="utf-8") as f:
    f.write(app_py)

print("✅ app.py создан (основной файл приложения)")
print("Размер файла:", len(app_py), "символов")
