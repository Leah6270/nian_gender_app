# -*- coding: utf-8 -*-
"""
nian_gender_app - 核心应用文件
功能：投票系统，带密码验证、唯一身份登记和防重复投票
"""

# 1. 导入所有必需的库
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

# 2. 创建Flask应用实例
app = Flask(__name__)

# 3. 应用配置
app.config['SECRET_KEY'] = 'Kathmanhuhu2018'  
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///database.db'  # 数据库文件路径
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 禁用警告
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # session有效期1小时

# 4. 初始化数据库
db = SQLAlchemy(app)

# ------------------------------------------------------------------
# 5. 数据库模型定义（创建3张核心表）
# ------------------------------------------------------------------

class VoteEvent(db.Model):
    """投票活动表：存储全局设置"""
    id = db.Column(db.Integer, primary_key=True)
    event_password = db.Column(db.String(80), default='wangnian2026')  # 统一PIN码
    correct_option = db.Column(db.String(2))  # 正确答案：'男孩'或'女孩'，初始为NULL
    end_date = db.Column(db.DateTime, nullable=False) # 必须设置截止日期
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Participant(db.Model):
    """参与者表：存储用户信息，防止重复投票"""
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), unique=True, nullable=False)  # 昵称（唯一）
    contact_info = db.Column(db.String(120), unique=True, nullable=False)  # 联系方式（唯一）
    has_voted = db.Column(db.Boolean, default=False)  # 是否已投票（关键字段）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Vote(db.Model):
    """投票记录表：存储每一张选票"""
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'))
    option_chosen = db.Column(db.String(2))  # '男孩' 或 '女孩'
    vote_time = db.Column(db.DateTime, default=datetime.utcnow)
    # 建立关系，方便查询
    participant = db.relationship('Participant', backref=db.backref('votes', lazy=True))

# ------------------------------------------------------------------
# 6. 辅助函数
# ------------------------------------------------------------------

def get_vote_statistics():
    """获取当前投票统计"""
    votes_a = Vote.query.filter_by(option_chosen='男孩').count()
    votes_b = Vote.query.filter_by(option_chosen='女孩').count()
    return {'男孩': votes_a, '女孩': votes_b}

def is_vote_active():
    """检查投票是否仍在有效期内"""
    event = VoteEvent.query.first()
    if not event or not event.end_date:
        return True # 如果没有设置截止日期，则默认允许投票
    
    from datetime import datetime
    now = datetime.utcnow()
    return now <= event.end_date # 当前时间小于等于截止时间则有效

def init_database():
    """初始化数据库，创建默认投票活动"""
    with app.app_context():
        # 创建所有表
        db.create_all()
        
        # 如果还没有投票活动，创建一个默认的
        if not VoteEvent.query.first():
            from datetime import datetime
            deadline = datetime(2026, 2, 16, 23, 59, 59)
            default_event = VoteEvent(
                event_password='LMN2026',
                end_date=deadline
            )
            db.session.add(default_event)
            db.session.commit()
            print("✅ 数据库初始化成功！")
            print("   默认PIN码：LMN2026")
            print("   数据库文件：database.db")

# ------------------------------------------------------------------
# 7. 路由定义（用户访问的各个页面）
# ------------------------------------------------------------------

@app.route('/')
def index():
    """首页：输入PIN码"""
    # 如果用户已经登录（在session中），直接跳转到相应页面
    if 'participant_id' in session:
        participant = Participant.query.get(session['participant_id'])
        if participant and participant.has_voted:
            return redirect(url_for('results'))
        elif participant and not participant.has_voted:
            return redirect(url_for('vote'))
    
    event = VoteEvent.query.first()
    deadline_passed = False
    deadline_str = "2026年2月17日"  # 固定提示字符串
    
    if event and event.end_date:
        from datetime import datetime
        now = datetime.utcnow()
        deadline_passed = now > event.end_date
    
    # 渲染模板时传递截止日期信息
    return render_template('index.html', deadline_passed=deadline_passed, deadline_str=deadline_str)

@app.route('/verify_pin', methods=['POST'])
def verify_pin():
    """验证PIN码"""
    pin = request.form.get('pin', '').strip()
    
    # 查询数据库中的活动
    event = VoteEvent.query.first()
    
    # 首先检查投票是否已截止
    if not is_vote_active():
        return render_template('index.html', error="投票截止啦，请等待开奖吧", deadline_passed=True, deadline_str="2026年2月17日")

    if event and pin == event.event_password:
        # PIN码正确，将event_id存入session
        session['event_id'] = event.id
        session.permanent = True
        return redirect(url_for('register'))
    else:
        # PIN码错误，返回错误信息
        return render_template('index.html', error="密码错误，请重新输入")

@app.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面：输入昵称和联系方式"""
    # 检查是否已验证PIN码
    if 'event_id' not in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        contact = request.form.get('contact', '').strip()
        
        # 验证输入
        if not nickname or not contact:
            return render_template('register.html', error="请填写所有字段")
        
        # 检查昵称和联系方式是否已存在
        if Participant.query.filter_by(nickname=nickname).first():
            return render_template('register.html', error="该昵称已被使用，请换一个")
        if Participant.query.filter_by(contact_info=contact).first():
            return render_template('register.html', error="该联系方式已被使用")
        
        # 创建新参与者
        try:
            new_participant = Participant(
                nickname=nickname,
                contact_info=contact
            )
            db.session.add(new_participant)
            db.session.commit()
            
            # 将参与者ID存入session，相当于"登录"
            session['participant_id'] = new_participant.id
            return redirect(url_for('vote'))
            
        except Exception as e:
            db.session.rollback()
            return render_template('register.html', error=f"注册失败：{str(e)}")
    
    # GET请求：显示注册表单
    return render_template('register.html')

@app.route('/vote', methods=['GET', 'POST'])
def vote():
    """投票页面：选择男孩或女孩"""
    # 检查是否已注册
    if 'participant_id' not in session:
        return redirect(url_for('index'))
    
    participant = Participant.query.get(session['participant_id'])
    if not participant:
        return redirect(url_for('index'))
    
    # 如果已经投过票，跳转到结果页
    if participant.has_voted:
        return redirect(url_for('results'))
    
    # 无论是GET还是POST请求，都先检查截止日期
    event = VoteEvent.query.first()
    if event and event.end_date:
        from datetime import datetime
        now = datetime.utcnow()
        if now > event.end_date:  # 当前时间已超过截止时间
            error_msg = f"投票已于2026年2月17日截止，无法投票。"
            
            # 如果是POST请求，返回错误
            if request.method == 'POST':
                return render_template('vote.html', error=error_msg)
            # 如果是GET请求，也显示错误
            else:
                return render_template('vote.html', error=error_msg, voting_closed=True)

    if request.method == 'POST':
        option = request.form.get('vote_option')
        
        if option not in ['男孩', '女孩']:
            return render_template('vote.html', error="请选择有效选项")
        
        try:
            # 记录投票
            new_vote = Vote(
                participant_id=participant.id,
                option_chosen=option
            )
            # 标记为已投票
            participant.has_voted = True
            
            db.session.add(new_vote)
            db.session.commit()
            
            return redirect(url_for('results'))
            
        except Exception as e:
            db.session.rollback()
            return render_template('vote.html', error=f"投票失败：{str(e)}")
    
    # GET请求：显示投票表单
    return render_template('vote.html')

@app.route('/results')
def results():
    """投票结果页面"""
    # 检查是否已投票
    if 'participant_id' not in session:
        return redirect(url_for('index'))
    
    participant = Participant.query.get(session['participant_id'])
    if not participant:
        return redirect(url_for('index'))
    
    # 获取统计数据和用户自己的选择
    stats = get_vote_statistics()
    user_vote = Vote.query.filter_by(participant_id=participant.id).first()
    
    return render_template('results.html', 
                         stats=stats,
                         user_choice=user_vote.option_chosen if user_vote else None,
                         total_votes=stats['男孩'] + stats['女孩'])

@app.route('/api/statistics')
def api_statistics():
    """API接口：返回JSON格式的统计数据（用于图表动态更新）"""
    stats = get_vote_statistics()
    return jsonify(stats)

@app.route('/check_status')
def check_status():
    """检查用户状态（用于恭喜页面）"""
    if 'participant_id' not in session:
        return redirect(url_for('index'))
    
    participant = Participant.query.get(session['participant_id'])
    if not participant:
        return redirect(url_for('index'))
    
    # 获取正确答案
    event = VoteEvent.query.first()
    user_vote = Vote.query.filter_by(participant_id=participant.id).first()
    
    if event and event.correct_option and user_vote:
        is_correct = (user_vote.option_chosen == event.correct_option)
        message = "哇哦，猜对了！请期待我们的小礼物~" if is_correct else "啊哦，猜错了，但是谢谢你的祝福！"
        return render_template('feedback.html', 
                             is_correct=is_correct,
                             message=message,
                             correct_answer=event.correct_option,
                             your_choice=user_vote.option_chosen)
    
    return render_template('feedback.html', 
                         message="尚未开奖",
                         correct_answer=None)

# ------------------------------------------------------------------
# 8. 管理后台路由（需要密码访问）
# ------------------------------------------------------------------

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """简易管理后台"""
    admin_password = "admin123"  
    
    if request.method == 'POST':
        password = request.form.get('password')
        if password == admin_password:
            session['is_admin'] = True
    
    # 检查管理员权限
    if not session.get('is_admin'):
        return render_template('admin_login.html')
    
    # 管理员已登录，显示数据
    participants = Participant.query.all()
    votes = Vote.query.all()
    event = VoteEvent.query.first()
    
    # 按选项分组
    votes_by_option = {
        '男孩': Vote.query.filter_by(option_chosen='男孩').all(),
        '女孩': Vote.query.filter_by(option_chosen='女孩').all()
    }

    stats = get_vote_statistics()  # 获取统计数据（男孩、女孩票数）
    total_votes = stats['男孩'] + stats['女孩']  # 计算总票数
    voted_count = Participant.query.filter_by(has_voted=True).count()  # 计算已投票人数
     
    return render_template('admin_dashboard.html',
                         participants=participants,
                         votes=votes,
                         votes_by_option=votes_by_option,
                         event=event,
                         stats=stats,
                         total_votes=total_votes, 
                         voted_count=voted_count)

@app.route('/admin/set_answer', methods=['POST'])
def set_answer():
    """设置正确答案（管理员操作）"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    answer = request.form.get('answer')
    if answer not in ['男孩', '女孩']:
        return jsonify({'error': 'Invalid answer'}), 400
    
    event = VoteEvent.query.first()
    if event:
        event.correct_option = answer
        db.session.commit()
        return jsonify({'success': True, 'answer': answer})
    
    return jsonify({'error': 'Event not found'}), 404

# ------------------------------------------------------------------
# 9. 应用启动
# ------------------------------------------------------------------

if __name__ == '__main__':
    # 初始化数据库（如果尚未初始化）
    init_database()
    
    print("\n" + "="*50)
    print("投票应用启动成功！")
    print("访问地址：http://127.0.0.1:5000")
    print("默认PIN码：LMN2026")
    print("管理后台：http://127.0.0.1:5000/admin (密码: admin123)")
    print("="*50 + "\n")
    
    # 启动Flask开发服务器
    # debug=True 表示调试模式，代码修改会自动重启
    # host='0.0.0.0' 可以让同一网络下的手机访问
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # vercel部署数据库初始化
    application = app
    try:
        with app.app_context():
            init_database()
    except Exception as e:
        print(f"数据库初始化警告: {e}")
