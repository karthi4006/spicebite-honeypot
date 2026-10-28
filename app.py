"""
WARNING: This application intentionally contains vulnerabilities for educational honeypot purposes.
DO NOT deploy this in a production environment without proper isolation.
"""

import os, re, json, uuid, sqlite3, hashlib, datetime, logging
from functools import wraps
from markupsafe import Markup
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, g, flash, abort)
from werkzeug.utils import secure_filename

# ── App Setup ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.secret_key = 'spicebite-honeypot-xK9mP-2024'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

DATABASE = 'database.db'; LOG_DIR = 'logs'; REVIEWS_FILE = 'reviews.json'
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── CSRF ─────────────────────────────────────────────────────────────────────
def generate_csrf():
    if '_csrf' not in session:
        session['_csrf'] = hashlib.sha256(os.urandom(32)).hexdigest()
    return session['_csrf']

def validate_csrf(t): return t and t == session.get('_csrf')
app.jinja_env.globals['csrf_token'] = generate_csrf

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    db = getattr(g, '_db', None)
    if db is None:
        db = g._db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(e):
    db = getattr(g, '_db', None)
    if db: db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
  	  id INTEGER PRIMARY KEY AUTOINCREMENT,
  	  username TEXT UNIQUE NOT NULL,
	  password TEXT NOT NULL,
    	  email TEXT UNIQUE,
   	  phone TEXT,
 	  card_number TEXT,
	  address TEXT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attack_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            endpoint TEXT, attack_type TEXT, payload TEXT,
            user_agent TEXT, extra TEXT
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT, username TEXT, password TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 0, user_agent TEXT
        );
        CREATE TABLE IF NOT EXISTS file_upload_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT, filename TEXT, extension TEXT,
            suspicious INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_agent TEXT, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS admin_login_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT, username TEXT, password TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_agent TEXT, attempt_number INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT, items TEXT, total REAL,
            transaction_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            card_last4 TEXT
        );
        INSERT OR IGNORE INTO users (username,password,email)
            VALUES ('john','password123','john@example.com');
        INSERT OR IGNORE INTO users (username,password,email)
            VALUES ('demo','demo1234','demo@spicebite.com');
        """)
        db.commit()

# ── Menu ──────────────────────────────────────────────────────────────────────
def get_menu():
    return {
        "desserts": [{"id":f"d{i}","name":n,"desc":d,"price":p,"emoji":e}
            for i,(n,d,p,e) in enumerate([
            ("Molten Lava Cake","Warm chocolate cake with gooey center",6.99,"images/molten_lava_cake.png"),
            ("Mango Panna Cotta","Silky Italian dessert with mango coulis",5.49,"images/panacota.png"),
            ("Churros and Dip","Crispy cinnamon sticks with chocolate sauce",4.99,"images/churros.png"),
            ("Tiramisu Cup","Classic Italian espresso dessert",6.49,"images/tiramisu.png"),
            ("Berry Cheesecake","New York style with fresh mixed berries",7.99,"images/berry.png"),
            ("Creme Brulee","French classic with caramelized sugar top",7.49,"images/creme_brulee.png"),
            ("Waffles and Cream","Belgian waffles with whipped cream",5.99,"images/waffles.png"),
            ("Gelato Trio","Three scoops of artisanal Italian gelato",6.99,"images/gelato.png"),
            ("Baklava Box","Honey-soaked phyllo pastry with mixed nuts",5.49,"images/baklav.jpeg"),
            ("Choco Fondue","Premium dark chocolate with seasonal fruits",8.99,"images/choco.png"),
            ("Matcha Ice Cream","Japanese green tea premium ice cream",5.99,"images/matcha_ice_tea.jpeg"),
            ("Caramel Flan","Classic Spanish flan with burnt caramel",5.49,"images/caramel.png"),
        ],1)],
        "spicy": [{"id":f"s{i}","name":n,"desc":d,"price":p,"emoji":e}
            for i,(n,d,p,e) in enumerate([
            ("Ghost Pepper Wings","Ultra-hot wings for the truly brave",12.99,"images/ghost_pepper_wings.jpeg"),
            ("Szechuan Noodles","Numbing spicy Chinese dan dan noodles",10.99,"images/noodles.jpeg"),
            ("Nashville Hot Chicken","Tennessee-style crispy fiery chicken",13.99,"images/hot_chicken.jpeg"),
            ("Spicy Tuna Roll","Fiery tuna with sriracha aioli and tobiko",9.99,"images/tuna.png"),
            ("Jalapeno Burger","Double patty with pickled jalapenos and cheese",14.99,"images/burger.jpeg"),
            ("Fire Ramen","Habanero broth with slow-braised pork belly",13.49,"images/ramen.jpeg"),
            ("Chili Crab","Singapore-style wok-tossed spicy crab",18.99,"images/crab.jpeg"),
            ("Tandoori Platter","Mixed Indian tandoor grilled meats and naan",16.99,"images/tandoori_platter.jpeg"),
            ("Sambal Shrimp","Malaysian style chili-garlic tiger shrimp",15.99,"images/shrimp.png"),
            ("Kimchi Fried Rice","Korean spicy fermented cabbage fried rice",9.99,"images/kimchi_fried_rice.jpeg"),
        ],1)],
        "noodles": [{"id":f"n{i}","name":n,"desc":d,"price":p,"emoji":e}
            for i,(n,d,p,e) in enumerate([
            ("Tonkotsu Ramen","Rich pork bone broth with chashu and egg",13.99,"images/ramen2.jpeg"),
            ("Pad Thai","Thai stir-fried rice noodles with peanuts",11.99,"images/pad_thai.jpeg"),
            ("Spaghetti Carbonara","Creamy guanciale egg yolk and pecorino",12.99,"images/spagheti.jpeg"),
            ("Udon Sukiyaki","Japanese thick udon in sweet soy broth",12.49,"images/udon.jpeg"),
            ("Singapore Mei Fun","Thin rice vermicelli with curry and prawns",10.99,"images/mei_fun.png"),
            ("Pho Bo","Vietnamese slow-simmered beef noodle soup",13.49,"images/pho_bo.png"),
            ("Dan Dan Mian","Sichuan sesame chili noodles with minced pork",10.99,"images/dan_dan.png"),
            ("Laksa","Malaysian coconut curry prawn noodle soup",12.99,"images/laksa.png"),
            ("Cacio e Pepe","Roman pepper and aged pecorino pasta",11.49,"images/casio.png"),
            ("Yakisoba","Japanese stir-fried wheat noodles and pork",10.49,"images/yaksibo.png"),
        ],1)],
        "pizza": [{"id":f"p{i}","name":n,"desc":d,"price":p,"emoji":e}
            for i,(n,d,p,e) in enumerate([
            ("Margherita","San Marzano tomato and buffalo mozzarella",11.99,"images/marg.png"),
            ("Truffle Prosciutto","Black truffle cream and San Daniele prosciutto",17.99,"images/truffle.png"),
            ("BBQ Chicken","Smoky BBQ sauce grilled chicken and red onion",14.99,"images/bbq.png"),
            ("Four Cheese","Mozzarella gorgonzola parmesan and ricotta",15.49,"images/four_cheese.png"),
            ("Veggie Supreme","Roasted peppers mushrooms olives and artichoke",12.99,"images/mushroom.png"),
            ("Pepperoni Classic","Double layered pepperoni and fresh mozzarella",13.99,"images/pepporoni.png"),
            ("Hawaiian Twist","Ham grilled pineapple and pickled jalapeno",12.49,"images/hawai.png"),
            ("Pesto Funghi","Basil pesto base with mixed wild mushrooms",14.49,"images/pesto.png"),
            ("Seafood Delight","Shrimp squid mussels garlic oil and parsley",16.99,"images/seafood.png"),
            ("Spicy Nduja","Calabrian spreadable salami with honey drizzle",15.49,"images/spicy.png"),
        ],1)],
        "beverages": [{"id":f"b{i}","name":n,"desc":d,"price":p,"emoji":e}
            for i,(n,d,p,e) in enumerate([
            ("Mango Lassi","Thick Indian yogurt and alphonso mango drink",3.99,"images/lassi.png"),
            ("Bubble Tea Taro","Taiwanese taro milk tea with tapioca pearls",4.99,"images/bubble.png"),
            ("Watermelon Slush","Fresh watermelon frozen slushie with mint",3.49,"images/watermelon.png"),
            ("Mint Lemonade","Fresh squeezed lemon with garden mint",3.99,"images/lemonade.png"),
            ("Rose Iced Tea","Floral rose petal cold brew jasmine tea",4.49,"images/rose_tea.png"),
            ("Cold Brew Coffee","12-hour steeped single origin Ethiopian",4.99,"images/coffee.png"),
            ("Strawberry Shake","Thick blended fresh strawberry milkshake",5.49,"images/strawberry.png"),
        ],1)],
        "fastfood": [{"id":f"f{i}","name":n,"desc":d,"price":p,"emoji":e}
            for i,(n,d,p,e) in enumerate([
            ("Smash Burger","Crispy double-smashed patty and secret sauce",12.99,"images/burger.jpeg"),
            ("Loaded Fries","Cheese sauce bacon jalapeno and sour cream",7.99,"images/loaded_fries.png"),
            ("Crispy Chicken Wrap","Southern fried chicken slaw and honey mustard",10.99,"images/chicken_wrap.png"),
            ("Corn Dog Bites","Mini honey cornmeal battered sausage bites",6.99,"images/corndog.png"),
            ("Mozzarella Sticks","Golden-fried with house marinara dipping sauce",6.49,"images/sticks.png"),
            ("Chili Cheese Dog","All-beef frank house chili and cheddar",8.99,"images/cheesedog.png"),
            ("Onion Rings","Beer-battered thick-cut sweet onion rings",5.99,"images/onion.png"),
            ("Nachos Grande","Tortilla chips loaded with all the toppings",8.49,"images/nachos.png"),
        ],1)],
    }

MENU = get_menu()

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_ip(): return request.headers.get('X-Forwarded-For', request.remote_addr)

def log_attack(attack_type, payload="", endpoint=None, extra=None):
    ip = get_ip(); ua = request.user_agent.string
    ep = endpoint or request.path
    ts = datetime.datetime.utcnow().isoformat()
    try:
        db = get_db()
        db.execute("INSERT INTO attack_logs (ip,endpoint,attack_type,payload,user_agent,extra) VALUES(?,?,?,?,?,?)",
            (ip,ep,attack_type,str(payload)[:2000],ua,json.dumps(extra) if extra else None))
        db.commit()
    except Exception as ex: logger.error(f"log err: {ex}")
    def _w(f,e):
        try:
            with open(os.path.join(LOG_DIR,f),'a') as fh: fh.write(json.dumps(e)+"\n")
        except: pass
    _w("glasstopf.json",{"sensor":"glasstopf","time":ts,"source":{"ip":ip,"port":0},
        "request":{"method":request.method,"uri":ep,"body":str(payload)[:500]},
        "attack_type":attack_type,"user_agent":ua})
    _w("cowrie.json",{"eventid":f"honeypot.web.{attack_type.lower().replace(' ','_')}",
        "timestamp":ts,"src_ip":ip,"message":f"Web honeypot: {attack_type} on {ep}",
        "payload":str(payload)[:500]})
    _w("dionaea.json",{"timestamp":ts,"type":"web_request","attack":attack_type,
        "remote_host":ip,"url":ep,"data":str(payload)[:500]})

SQLI_RE = [r"'\s*(or|and)\s*'?\d",r"--\s*$",r"/\*.*\*/",
    r"\bunion\b.*\bselect\b",r"\bdrop\b.*\btable\b",r"\binsert\b.*\binto\b",
    r"xp_cmdshell",r";.*--",r"\b1\s*=\s*1\b",r"\bor\b\s+\d+=\d+",
    r"\bsleep\b\s*\(",r"\bbenchmark\b\s*\("]
XSS_RE = [r"<script",r"javascript:",r"onerror\s*=",r"onload\s*=",
    r"eval\s*\(",r"document\.cookie",r"alert\s*\(",r"<iframe",
    r"<img[^>]+on\w+",r"on\w+\s*=\s*['\"]"]
SUSP_EXTS = {'.php','.exe','.sh','.py','.pl','.rb','.asp','.aspx',
             '.bat','.cmd','.ps1','.jar','.war','.cgi'}

def detect_sqli(t): return any(re.search(p,t,re.I) for p in SQLI_RE)
def detect_xss(t):  return any(re.search(p,t,re.I) for p in XSS_RE)

BADGE_MAP = {'SQL Injection':'sqli','SQL Injection Error':'sqli','Reflected XSS':'xss',
    'XSS in Review':'xss','Suspicious Upload':'upload','Malware Upload':'upload',
    'Admin Brute Force':'brute','Debug Endpoint Access':'debug',
    'DevTools Opened':'devtools','404 Probe':'fourohfour','Checkout':'info','Sensitive Data Brute Force':'brute'
}

@app.template_global()
def badge(t):
    return Markup(f'<span class="badge-attack badge-{BADGE_MAP.get(t,"other")}">{t}</span>')

def login_required(f):
    @wraps(f)
    def dec(*a,**kw):
        if not session.get('user'):
            flash('Please sign in to continue.','warning')
            return redirect(url_for('login',next=request.path))
        return f(*a,**kw)
    return dec

def admin_required(f):
    @wraps(f)
    def dec(*a,**kw):
        if not session.get('admin'):
            flash('Admin access required.','danger')
            return redirect(url_for('admin_login'))
        return f(*a,**kw)
    return dec

@app.context_processor
def inject_globals():
    cart = session.get('cart',{})
    return dict(
        cart_count=sum(v['qty'] for v in cart.values()),
        wish_count=len(session.get('wishlist',[])),
        categories=list(MENU.keys()),
        current_user=session.get('user'),
        is_admin=session.get('admin',False),
    )

# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def index():
    import random
    f=[]
    for cat,items in MENU.items(): f.extend(items[:2])
    random.shuffle(f)
    return render_template('index.html',featured=f[:8])

@app.route('/category/<cat>')
def category(cat):
    if cat not in MENU: abort(404)
    return render_template('category.html',cat=cat.title(),items=MENU[cat],cat_key=cat)

@app.route('/search')
def search():
    q=request.args.get('q','').strip()
    if q and detect_xss(q): log_attack('Reflected XSS',q)
    results=[]
    if q:
        ql=q.lower()
        for cat,items in MENU.items():
            for item in items:
                if ql in item['name'].lower() or ql in item['desc'].lower():
                    results.append({**item,'category':cat})
    return render_template('search.html',query=q,results=results)

# ── AUTH ──────────────────────────────────────────────────────────────────────
@app.route('/signup',methods=['GET','POST'])
def signup():
    if session.get('user'): return redirect(url_for('index'))
    error=None
    if request.method=='POST':
        username=request.form.get('username','').strip()
        email=request.form.get('email','').strip()
        password=request.form.get('password','')
        confirm=request.form.get('confirm_password','')
        if not username or not password or not email: error='All fields are required.'
        elif len(username)<3: error='Username must be at least 3 characters.'
        elif len(password)<6: error='Password must be at least 6 characters.'
        elif password!=confirm: error='Passwords do not match.'
        else:
            try:
                db=get_db()
                db.execute("INSERT INTO users (username,password,email) VALUES(?,?,?)",(username,password,email))
                db.commit()
                session['user']=username
                flash(f'Welcome to SpiceBite, {username}! 🎉','success')
                return redirect(request.args.get('next') or url_for('index'))
            except sqlite3.IntegrityError: error='Username or email already registered.'
    return render_template('signup.html',error=error)

@app.route('/login',methods=['GET','POST'])
def login():
    if session.get('user'): return redirect(url_for('index'))
    error=None
    if request.method=='POST':
        username=request.form.get('username','')
        password=request.form.get('password','')
        ip,ua=get_ip(),request.user_agent.string
        sqli=detect_sqli(username) or detect_sqli(password)
        if sqli: log_attack('SQL Injection',f"user={username}&pass={password}")
        db=get_db(); row=None
        try:
            # INTENTIONALLY VULNERABLE — honeypot trap
            row=db.execute(f"SELECT * FROM users WHERE username='{username}' AND password='{password}'").fetchone()
        except Exception as e: log_attack('SQL Injection Error',str(e))
        db.execute("INSERT INTO login_attempts (ip,username,password,success,user_agent) VALUES(?,?,?,?,?)",
            (ip,username,password[:120],1 if row else 0,ua))
        db.commit()
        if row:
            session['user']=row['username']
            flash(f'Welcome back, {row["username"]}! 🔥','success')
            return redirect(request.form.get('next') or request.args.get('next') or url_for('index'))
        error='Invalid credentials.' if not sqli else 'An error occurred.'
    return render_template('login.html',error=error,next=request.args.get('next',''))
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()

    user = db.execute(
        "SELECT username,email,phone,card_number,account_number,password FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    sensitive_visible = False

    if request.method == "POST":
        entered = request.form.get("password")

        if entered == user["password"]:   # intentionally weak for honeypot
            sensitive_visible = True

            logging.warning(
                f"[HONEYPOT] Sensitive data accessed by user {user['username']} IP:{request.remote_addr}"
            )

        else:
            flash("Incorrect password", "danger")

    return render_template(
        "profile.html",
        user=user,
        sensitive_visible=sensitive_visible
    )
@app.route('/profile/unlock', methods=['POST'])
@login_required
def unlock_sensitive():

    password = request.form.get("password","")

    db = get_db()

    row = db.execute(
        "SELECT password FROM users WHERE username=?",
        (session['user'],)
    ).fetchone()

    # Detect attacks
    if detect_sqli(password):
        log_attack("SQL Injection", password)

    if detect_xss(password):
        log_attack("Reflected XSS", password)

    # Wrong password attempts = brute force
    if password != row["password"]:
        log_attack("Sensitive Data Brute Force", password)

        flash("Incorrect password.", "danger")
        return redirect(url_for("profile"))

    user = db.execute(
        "SELECT username,email,phone,card_number,address FROM users WHERE username=?",
        (session['user'],)
    ).fetchone()

    return render_template("profile.html", user=user, unlocked=True)



@app.route('/logout')
def logout():
    u=session.pop('user',None)
    session.pop('cart',None); session.pop('wishlist',None)
    flash(f'Goodbye{", "+u if u else ""}! 👋','info')
    return redirect(url_for('index'))

# ── CART ──────────────────────────────────────────────────────────────────────
@app.route('/cart')
@login_required
def cart():
    data=session.get('cart',{}); items=[]; total=0
    for iid,info in data.items():
        sub=info['price']*info['qty']; total+=sub
        items.append({**info,'id':iid,'subtotal':sub})
    return render_template('cart.html',items=items,total=round(total,2))

@app.route('/cart/add',methods=['POST'])
@login_required
def cart_add():
    iid = request.form.get('item_id','')
    name = request.form.get('name','')
    price = float(request.form.get('price',0))
    emoji = request.form.get('emoji')   # ✅ ADD THIS LINE

    cart = session.get('cart',{})

    if iid in cart:
        cart[iid]['qty'] += 1
    else:
        cart[iid] = {
            'name': name,
            'price': price,
            'qty': 1,
            'emoji': emoji   # ✅ ADD THIS LINE
        }

    session['cart'] = cart
    flash(f'"{name}" added to cart! 🛒','success')
    return redirect(request.referrer or url_for('index'))


@app.route('/cart/remove/<iid>')
@login_required
def cart_remove(iid):
    cart=session.get('cart',{}); cart.pop(iid,None); session['cart']=cart
    return redirect(url_for('cart'))

@app.route('/cart/update',methods=['POST'])
@login_required
def cart_update():
    iid=request.form.get('item_id'); qty=int(request.form.get('qty',1))
    cart=session.get('cart',{})
    if iid in cart:
        if qty<=0: cart.pop(iid)
        else: cart[iid]['qty']=qty
    session['cart']=cart
    return redirect(url_for('cart'))

# ── WISHLIST ──────────────────────────────────────────────────────────────────
@app.route('/wishlist')
@login_required
def wishlist():
    return render_template('wishlist.html',items=session.get('wishlist',[]))

@app.route('/wishlist/add',methods=['POST'])
@login_required
def wishlist_add():
    iid=request.form.get('item_id'); name=request.form.get('name')
    price=float(request.form.get('price',0)); emoji=request.form.get('emoji','')
    wl=session.get('wishlist',[])
    if not any(i['id']==iid for i in wl):
        wl.append({'id':iid,'name':name,'price':price,'emoji':emoji})
        flash(f'"{name}" saved to wishlist! ❤️','info')
    else: flash(f'"{name}" already in wishlist.','warning')
    session['wishlist']=wl
    return redirect(request.referrer or url_for('index'))

@app.route('/wishlist/remove/<iid>')
@login_required
def wishlist_remove(iid):
    session['wishlist']=[i for i in session.get('wishlist',[]) if i['id']!=iid]
    return redirect(url_for('wishlist'))

# ── CHECKOUT ──────────────────────────────────────────────────────────────────
@app.route('/checkout',methods=['GET','POST'])
@login_required
def checkout():
    data=session.get('cart',{})
    if not data: flash('Cart is empty!','warning'); return redirect(url_for('cart'))
    if request.method=='POST':
        if not validate_csrf(request.form.get('csrf_token')):
            flash('Session expired.','danger'); return redirect(url_for('checkout'))
        card=request.form.get('card_number','').replace(' ','')
        card_last4=card[-4:] if len(card)>=4 else '0000'
        items=[]; total=0
        for iid,info in data.items():
            sub=info['price']*info['qty']; total+=sub
            items.append({**info,'subtotal':sub})
        txn=str(uuid.uuid4()).upper().replace('-','')[:16]
        db=get_db()
        db.execute("INSERT INTO orders (user,items,total,transaction_id,card_last4) VALUES(?,?,?,?,?)",
            (session['user'],json.dumps(items),round(total,2),txn,card_last4))
        db.commit()
        log_attack('Checkout',f"user={session['user']}&total={total:.2f}")
        session['cart']={}
        return render_template('bill.html',items=items,total=round(total,2),txn_id=txn,
            card_last4=card_last4,timestamp=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            username=session['user'])
    items=[]; total=0
    for iid,info in data.items():
        sub=info['price']*info['qty']; total+=sub
        items.append({**info,'id':iid,'subtotal':sub})
    return render_template('checkout.html',items=items,total=round(total,2))

# ── REVIEWS ───────────────────────────────────────────────────────────────────
def load_reviews():
    if os.path.exists(REVIEWS_FILE):
        try: return json.load(open(REVIEWS_FILE))
        except: pass
    return []

def save_reviews(data):
    with open(REVIEWS_FILE,'w') as f: json.dump(data,f,indent=2)

@app.route('/reviews',methods=['GET','POST'])
def reviews():
    all_rev=load_reviews()
    if request.method=='POST':
        name=request.form.get('reviewer_name','').strip()
        rating=request.form.get('rating','5')
        text=request.form.get('review_text','').strip()
        ip,ua=get_ip(),request.user_agent.string
        if not name or not text:
            flash('Name and review text are required.','danger')
            return redirect(url_for('reviews'))
        if detect_xss(text) or detect_xss(name): log_attack('XSS in Review',f"{name}: {text}")
        file=request.files.get('attachment')
        if file and file.filename:
            fn=secure_filename(file.filename); ext=os.path.splitext(fn)[1].lower()
            susp=ext in SUSP_EXTS; content=file.read(2048); notes=[]
            if any(s in content for s in [b'<script',b'<?php',b'#!/',b'<%']):
                notes.append('malicious'); susp=True
                log_attack('Malware Upload',fn,extra={'fn':fn,'ext':ext})
            try:
                db=get_db()
                db.execute("INSERT INTO file_upload_logs (ip,filename,extension,suspicious,user_agent,notes) VALUES(?,?,?,?,?,?)",
                    (ip,fn,ext,1 if susp else 0,ua,','.join(notes)))
                db.commit()
            except: pass
            if susp: log_attack('Suspicious Upload',fn,extra={'ext':ext}); flash(f'File flagged by security scanner.','warning')
            else: flash('Photo attached.','success')
        all_rev.insert(0,{'id':str(uuid.uuid4())[:8],'name':name,'rating':int(rating),
            'text':text,'timestamp':datetime.datetime.now().strftime('%d %b %Y'),
            'user':session.get('user','guest')})
        save_reviews(all_rev[:200])
        flash('Review submitted! Thank you 🙏','success')
        return redirect(url_for('reviews'))
    return render_template('reviews.html',reviews=all_rev[:20])

# ── ADMIN ─────────────────────────────────────────────────────────────────────
ADMIN_ATTEMPTS={}

@app.route('/admin-login', methods=['GET','POST'])
def admin_login():
    error=None
    ip=get_ip()

    if request.method=='POST':
        username=request.form.get('username','')
        password=request.form.get('password','')
        ua=request.user_agent.string

        ADMIN_ATTEMPTS[ip]=ADMIN_ATTEMPTS.get(ip,0)+1
        n=ADMIN_ATTEMPTS[ip]

        db=get_db()
        db.execute("INSERT INTO admin_login_logs (ip,username,password,user_agent,attempt_number) VALUES(?,?,?,?,?)",
            (ip,username,password[:120],ua,n))
        db.commit()

        if n>3:
            log_attack('Admin Brute Force',f"user={username}",extra={'attempts':n})

        if username=='superadmin' and password=='Sp!ceB1te@dm1n':
            session.clear()
            session['admin']=True
            ADMIN_ATTEMPTS[ip]=0
            return redirect(url_for('admin_dashboard'))

        error='Access denied. This attempt has been logged.'

    return render_template('admin_login.html',error=error)

@app.route('/admin-logout')
def admin_logout():
    session.pop('admin', None)   # only remove admin session
    flash("Admin logged out successfully.", "info")
    return redirect(url_for('admin_login'))

@app.route('/admin-dashboard')
@admin_required
def admin_dashboard():
    db=get_db()
    attacks=db.execute("SELECT * FROM attack_logs ORDER BY timestamp DESC LIMIT 300").fetchall()
    logins=db.execute("SELECT * FROM login_attempts ORDER BY timestamp DESC LIMIT 150").fetchall()
    uploads=db.execute("SELECT * FROM file_upload_logs ORDER BY timestamp DESC LIMIT 150").fetchall()
    adm=db.execute("SELECT * FROM admin_login_logs ORDER BY timestamp DESC LIMIT 150").fetchall()
    orders=db.execute("SELECT * FROM orders ORDER BY timestamp DESC LIMIT 50").fetchall()
    users=db.execute("SELECT id,username,email,created_at FROM users ORDER BY created_at DESC").fetchall()
    tc={}; hourly={}; daily={}
    for r in attacks:
        tc[r['attack_type']]=tc.get(r['attack_type'],0)+1
        try:
            h=r['timestamp'][:13]; hourly[h]=hourly.get(h,0)+1
            d=r['timestamp'][:10]; daily[d]=daily.get(d,0)+1
        except: pass
    return render_template('admin_dashboard.html',
        attacks=attacks,logins=logins,uploads=uploads,admin_log=adm,
        orders=orders,users=users,
        type_counts=json.dumps(tc),hourly=json.dumps(hourly),daily=json.dumps(daily),
        total_attacks=len(attacks),
        suspicious_uploads=sum(1 for u in uploads if u['suspicious']),
        failed_logins=sum(1 for l in logins if not l['success']),
        total_orders=len(orders),total_users=len(users))

@app.route('/admin-dashboard/api/stats')
@admin_required
def admin_stats_api():
    db=get_db()
    rows=db.execute("SELECT attack_type, COUNT(*) c FROM attack_logs GROUP BY attack_type").fetchall()
    recent=db.execute("SELECT * FROM attack_logs ORDER BY timestamp DESC LIMIT 30").fetchall()
    total=db.execute("SELECT COUNT(*) FROM attack_logs").fetchone()[0]
    return jsonify({'attack_types':{r['attack_type']:r['c'] for r in rows},
        'recent':[dict(r) for r in recent],'total':total,
        'ts':datetime.datetime.utcnow().isoformat()})

@app.route('/api/debug')
def api_debug():
    params=dict(request.args)
    log_attack('Debug Endpoint Access',json.dumps(params),extra={'params':params})
    return jsonify({"status":"ok","version":"2.1.4","env":"production",
        "message":"Nothing interesting here.","secret_key":"***REDACTED***"})

@app.route('/api/devtools-ping',methods=['POST'])
def devtools_ping():
    data=request.get_json(silent=True) or {}
    log_attack('DevTools Opened',json.dumps(data),extra=data)
    return jsonify({'ok':True})

@app.errorhandler(404)
def not_found(e):
    log_attack('404 Probe',request.path)
    return render_template('404.html'),404

@app.errorhandler(413)
def too_large(e):
    flash('File too large. Max 16MB.','danger')
    return redirect(url_for('reviews'))

@app.errorhandler(500)
def server_error(e):
    return render_template('404.html',msg="Internal server error."),500
@app.route('/favicon.ico')
def favicon():
    return '', 204


if __name__=='__main__':
    init_db()
    app.run(debug=True,host='0.0.0.0',port=5000)
