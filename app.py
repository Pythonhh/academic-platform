from flask import Flask, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from models import db, User, Post, Comment, Vote, PostView, AcademicFeatures, PostCategory, Report
from datetime import datetime, timedelta
import pytz
from utils import contains_profanity, clean_text
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yeni-nesil-akademik-forum-key-12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///forum.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB max

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def check_bans():
    if current_user.is_authenticated and current_user.is_banned:
        if current_user.ban_expires_at and current_user.ban_expires_at < datetime.utcnow():
            # Ban has expired
            current_user.is_banned = False
            current_user.ban_reason = None
            current_user.ban_expires_at = None
            db.session.commit()
            return

        if request.endpoint not in ['static', 'logout', 'banned_page', 'check_bans']:
            return redirect(url_for('banned_page'))

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

@app.template_filter('turkish_time')
def turkish_time_filter(dt):
    if dt is None:
        return ""
    # Assuming dt is stored as naive UTC or naive local (old).
    # If stored as naive UTC (standard practice):
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    
    tr_tz = pytz.timezone('Europe/Istanbul')
    tr_dt = dt.astimezone(tr_tz)
    return tr_dt.strftime('%d.%m.%Y %H:%M')

@app.before_request
def restrict_banned_users():
    if current_user.is_authenticated and current_user.is_banned:
        if request.endpoint and (
            'static' in request.endpoint or 
            request.endpoint in ['banned_page', 'logout']
        ):
            return
            
        return redirect(url_for('banned_page'))

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    query = request.args.get('q', '').strip()
    category_slug = request.args.get('cat')
    
    posts_q = Post.query.join(User).filter(User.is_banned == False)
    
    if query:
        posts_q = posts_q.filter(
            (Post.title.ilike(f'%{query}%')) | 
            (Post.content.ilike(f'%{query}%'))
        )
    
    if category_slug:
        cat_enum = None
        if category_slug == 'experience': cat_enum = PostCategory.EXPERIENCE
        elif category_slug == 'question': cat_enum = PostCategory.QUESTION
        elif category_slug == 'advice': cat_enum = PostCategory.ADVICE
        elif category_slug == 'general': cat_enum = PostCategory.GENERAL
        
        if cat_enum:
            posts_q = posts_q.filter(Post.category == cat_enum)

    posts = posts_q.order_by(Post.created_at.desc()).paginate(page=page, per_page=10)
        
    return render_template('index.html', posts=posts, query=query, current_cat=category_slug)

@app.route('/banned', methods=['GET', 'POST'])
def banned_page():
    if not current_user.is_authenticated or not current_user.is_banned:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        appeal = request.form.get('appeal')
        if appeal:
            current_user.ban_appeal_reason = appeal
            db.session.commit()
            flash('Ban itirazınız gönderildi. Yönetici inceleyecek.', 'success')
            
    return render_template('banned.html', user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Read KVKK text
    try:
        with open('kvkk.txt', 'r', encoding='utf-8') as f:
            kvkk_text = f.read()
    except:
        kvkk_text = "KVKK Aydınlatma Metni bulunamadı."

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        university = request.form.get('university')
        bio = request.form.get('bio')
        agreed = request.form.get('kvkk_check')

        if not agreed:
            flash('KVKK metnini onaylamanız gerekmektedir.', 'error')
            return redirect(url_for('register'))

        if contains_profanity(username) or contains_profanity(university) or contains_profanity(bio):
            flash('Kullanıcı adı, üniversite veya biyografide yasaklı kelimeler tespit edildi.', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten alınmış.', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username, university=university, bio=bio, agreed_kvkk=datetime.utcnow())
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('index'))
    return render_template('register.html', kvkk_text=kvkk_text)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            # Check if user is banned
            if user.is_banned:
                # Check if ban has expired
                if user.ban_expires_at and user.ban_expires_at < datetime.utcnow():
                    user.is_banned = False
                    user.ban_reason = None
                    user.ban_expires_at = None
                    db.session.commit()
                    flash('Ban süreniz doldu, tekrar hoş geldiniz.', 'success')
                else:
                    # User is still banned. 
                    # We MUST log them in so they can access the /banned page and appeal.
                    login_user(user)
                    return redirect(url_for('banned_page'))

            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Giriş başarısız. Kullanıcı adı veya şifre yanlış.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    return redirect(url_for('view_profile', username=current_user.username))

@app.route('/u/<username>')
def view_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('profile.html', user=user)

@app.route('/report/<int:user_id>', methods=['POST'])
@login_required
def report_user(user_id):
    if user_id == current_user.id:
        flash('Kendinizi şikayet edemezsiniz.', 'error')
        return redirect(url_for('view_profile', username=current_user.username))
        
    user_to_report = User.query.get_or_404(user_id)
    reason = request.form.get('reason')
    
    if not reason:
        flash('Lütfen bir sebep belirtin.', 'error')
        return redirect(url_for('view_profile', username=user_to_report.username))
        
    new_report = Report(reporter_id=current_user.id, reported_user_id=user_id, reason=reason)
    db.session.add(new_report)
    db.session.commit()
    
    flash('Kullanıcı şikayet edildi. Yönetim inceleyecektir.', 'success')
    return redirect(url_for('view_profile', username=user_to_report.username))

@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    # Check if user is author or admin
    if post.author_id != current_user.id and not current_user.is_admin:
        abort(403)
        
    db.session.delete(post)
    db.session.commit()
    flash('Gönderi başarıyla silindi.', 'success')
    return redirect(url_for('index'))

@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    post_id = comment.post_id
    
    # Check if user is author or admin
    if comment.author_id != current_user.id and not current_user.is_admin:
        abort(403)
        
    db.session.delete(comment)
    db.session.commit()
    flash('Yorum başarıyla silindi.', 'success')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/admin/reports')
@login_required
def admin_reports():
    if not current_user.is_admin:
        abort(403)
    reports = Report.query.filter_by(is_resolved=False).order_by(Report.created_at.desc()).all()
    banned_users = User.query.filter_by(is_banned=True).all()
    return render_template('admin_reports.html', reports=reports, banned_users=banned_users)

@app.route('/admin/resolve_report/<int:report_id>')
@login_required
def resolve_report(report_id):
    if not current_user.is_admin:
        abort(403)
    report = Report.query.get_or_404(report_id)
    report.is_resolved = True
    db.session.commit()
    flash('Şikayet çözüldü olarak işaretlendi.', 'success')
    return redirect(url_for('admin_reports'))

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    new_username = request.form.get('username')
    university = request.form.get('university')
    bio = request.form.get('bio')
    password = request.form.get('password')
    
    # Image Upload
    if 'profile_image' in request.files:
        file = request.files['profile_image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            # Make unique to prevent overwrite/caching issues
            unique_filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}_{filename}"
            file.save(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], unique_filename))
            current_user.profile_image = unique_filename

    if contains_profanity(university) or contains_profanity(bio) or (new_username and contains_profanity(new_username)):
        flash('Yasaklı kelime tespit edildi. Profil güncellenemedi.', 'error')
        return redirect(url_for('profile'))

    # Handle Username Change
    if new_username and new_username != current_user.username:
        if not current_user.can_change_username:
            days_left = current_user.days_until_username_change
            flash(f'Kullanıcı adınızı değiştirmek için {days_left} gün daha beklemelisiniz.', 'gray-error')
        else:
            existing_user = User.query.filter_by(username=new_username).first()
            if existing_user:
                flash('Bu kullanıcı adı maalesef alınmış.', 'gray-error') # Desired aesthetic
            else:
                current_user.username = new_username
                current_user.last_username_change = datetime.utcnow()
                flash('Kullanıcı adı başarıyla değiştirildi.', 'success')

    current_user.university = university
    current_user.bio = bio
    
    if password:
        current_user.set_password(password)

    db.session.commit()
    flash('Profil bilgileri güncellendi.', 'success')
    return redirect(url_for('profile'))



@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category_str = request.form.get('category')
        
        if contains_profanity(title) or contains_profanity(content):
             flash('İçerikte yasaklı kelimeler bulundu!', 'error')
             return redirect(url_for('create_post'))

        try:
            category = PostCategory(category_str)
        except ValueError:
            flash('Geçersiz kategori seçimi.', 'error')
            return redirect(url_for('create_post'))

        new_post = Post(title=title, content=content, category=category, author=current_user)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('create_post.html')

@app.route('/post/<int:post_id>', methods=['GET'])
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    # Handle view counting (Unique per user)
    viewer_id = current_user.id if current_user.is_authenticated else None
    
    # If authenticated, check if they viewed before
    should_count = False
    if current_user.is_authenticated:
        view = PostView.query.filter_by(post_id=post.id, user_id=current_user.id).first()
        if not view:
            should_count = True
            db.session.add(PostView(post_id=post.id, user_id=current_user.id))
    
    if should_count:
        post.view_count += 1
        db.session.commit()

    # Calculate user's current votes on academic features if logged in
    user_votes = {}
    if current_user.is_authenticated:
        main_vote = Vote.query.filter_by(user_id=current_user.id, post_id=post.id).first()
        academic_votes = AcademicFeatures.query.filter_by(user_id=current_user.id, post_id=post.id).all()
        
        for v in academic_votes:
            user_votes[v.type] = v.value
            
        if main_vote:
            user_votes['main_vote'] = main_vote.value

    # Filter comments from banned users
    # We only want top-level comments here. Replies will be accessed via comment.replies
    all_comments = [c for c in post.comments if not c.author.is_banned]
    top_level_comments = [c for c in all_comments if c.parent_id is None]
    
    # Sort by date desc
    top_level_comments.sort(key=lambda x: x.created_at, reverse=True)

    return render_template('post_detail.html', post=post, user_votes=user_votes, comments=top_level_comments)

@app.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content')
    parent_id = request.form.get('parent_id')
    
    if not content or not content.strip():
        flash('Yorum içeriği boş olamaz.', 'error')
        return redirect(url_for('view_post', post_id=post_id))
    
    if contains_profanity(content):
        flash('Yorumunuz uygunsuz ifadeler içeriyor.', 'error')
        return redirect(url_for('view_post', post_id=post_id))
    
    # Check parent if reply
    parent = None
    if parent_id:
        try:
            parent_id = int(parent_id)
            parent = Comment.query.get(parent_id)
            # Ensure parent belongs to the same post
            if not parent or parent.post_id != post_id:
                parent = None
        except ValueError:
            parent = None
            
    new_comment = Comment(
        content=clean_text(content), 
        author=current_user, 
        post=post,
        created_at=datetime.utcnow(),
        parent_id=parent.id if parent else None
    )
    
    db.session.add(new_comment)
    db.session.commit()
    
    flash('Yorumunuz eklendi.', 'success')
    return redirect(url_for('view_post', post_id=post_id))


@app.route('/vote/<int:post_id>/<string:action>')
@login_required
def vote_post(post_id, action):
    post = Post.query.get_or_404(post_id)
    existing_vote = Vote.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    
    val = 1 if action == 'up' else -1
    
    if existing_vote:
        if existing_vote.value == val:
            db.session.delete(existing_vote) # Toggle off
        else:
            existing_vote.value = val # Change vote
    else:
        new_vote = Vote(user_id=current_user.id, post_id=post.id, value=val)
        db.session.add(new_vote)
    
    db.session.commit()
    return redirect(url_for('view_post', post_id=post.id))

@app.route('/vote_academic/<int:post_id>/<string:vtype>', methods=['POST'])
@login_required
def vote_academic(post_id, vtype):
    if vtype not in ['realism_score', 'is_experience', 'is_wish_knew']:
        abort(400)
    
    value = int(request.form.get('value', 1))

    existing = AcademicFeatures.query.filter_by(
        user_id=current_user.id, 
        post_id=post_id, 
        type=vtype
    ).first()

    if existing:
        if vtype in ['is_experience', 'is_wish_knew']:
            db.session.delete(existing)
        else:
            existing.value = value
    else:
        new_feat = AcademicFeatures(user_id=current_user.id, post_id=post_id, type=vtype, value=value)
        db.session.add(new_feat)
    
    db.session.commit()
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/report_post/<int:post_id>', methods=['POST'])
@login_required
def report_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id == current_user.id:
        flash('Kendi gönderinizi şikayet edemezsiniz.', 'error')
        return redirect(url_for('view_post', post_id=post_id))
        
    reason = request.form.get('reason')
    if not reason:
        flash('Lütfen sebep belirtin.', 'error')
        return redirect(url_for('view_post', post_id=post_id))
        
    new_report = Report(
        reporter_id=current_user.id, 
        reported_post_id=post_id, 
        reported_user_id=post.author_id, # Include author to prevent potential NULL constraint error
        reason=reason
    )
    db.session.add(new_report)
    db.session.commit()
    
    flash('Gönderi şikayet edildi.', 'success')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/ban/<int:user_id>', methods=['POST'])
@login_required
def ban_user(user_id):
    if not current_user.is_admin:
        abort(403)
        
    user_to_ban = User.query.get_or_404(user_id)
    reason = request.form.get('reason', 'Kural ihlali')
    duration = request.form.get('duration') # e.g., "1_day", "7_days", "permanent"
    
    user_to_ban.is_banned = True
    user_to_ban.ban_reason = reason
    
    if duration == '1_day':
        user_to_ban.ban_expires_at = datetime.utcnow() + timedelta(days=1)
    elif duration == '7_days':
        user_to_ban.ban_expires_at = datetime.utcnow() + timedelta(days=7)
    elif duration == '30_days':
        user_to_ban.ban_expires_at = datetime.utcnow() + timedelta(days=30)
    else:
        user_to_ban.ban_expires_at = None # Permanent
        
    db.session.commit()
    flash(f'Kullanıcı banlandı: {user_to_ban.username}', 'success')
    return redirect(url_for('index'))

@app.route('/unban/<int:user_id>', methods=['POST'])
@login_required
def unban_user(user_id):
    if not current_user.is_admin:
        abort(403)
        
    user_to_unban = User.query.get_or_404(user_id)
    user_to_unban.is_banned = False
    user_to_unban.ban_reason = None
    user_to_unban.ban_expires_at = None
    user_to_unban.ban_appeal_reason = None
    db.session.commit()
    
    flash(f'{user_to_unban.username} yasağı kaldırıldı.', 'success')
    return redirect(request.referrer or url_for('admin_reports'))

@app.route('/reject_appeal/<int:user_id>', methods=['POST'])
@login_required
def reject_appeal(user_id):
    if not current_user.is_admin:
        abort(403)
        
    user_to_reject = User.query.get_or_404(user_id)
    
    # Just clear the appeal message so it drops out of the "Requests" list
    # Optionally we could store "appeal rejected" status, but clearing is enough for now
    user_to_reject.ban_appeal_reason = None
    db.session.commit()
    
    flash(f'{user_to_reject.username} kullanıcısının itirazı reddedildi.', 'info')
    return redirect(request.referrer or url_for('admin_reports'))

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    try:
        user = User.query.get(current_user.id)
        if user:
            # Delete user - SQLAlchemy cascades defined in models.py will handle:
            # - User's posts (and their comments/votes)
            # - User's comments
            # - User's votes
            # - User's academic votes
            # - User's post views
            # - Reports related to user
            db.session.delete(user)
            db.session.commit()
            
            logout_user()
            flash('Hesabınız ve tüm verileriniz başarıyla silindi. Sizi özleyeceğiz...', 'success')
            return redirect(url_for('index'))
        else:
            flash('Hesap bulunamadı.', 'error')
            return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        # Log error in production
        print(f"Delete Account Error: {e}")
        flash('Hesap silinirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.', 'error')
        return redirect(url_for('profile'))


if __name__ == '__main__':
    with app.app_context():
        # THIS WILL WIPE DATA TO FIX SCHEMA ERROR - DISABLED FOR PERSISTENCE
        # db.drop_all() 
        db.create_all()
        # Create default admin if not exists (you can change username later)
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', is_admin=True, agreed_kvkk=datetime.utcnow())
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin kullanicisi olusturuldu.")
            
        print("Veritabani guncellendi.")
    app.run(debug=True)
