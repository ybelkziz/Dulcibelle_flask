from flask import Flask, render_template, request, redirect, url_for
from extensions import db   # <-- import depuis extensions
from flask import session, flash
from flask_wtf.csrf import CSRFProtect
from functools import wraps
from flask_mail import Mail, Message
from datetime import datetime
import os
from dotenv import load_dotenv
from flask_talisman import Talisman

# Charger les variables d'environnement depuis .env
load_dotenv()

# Création de l'application Flask
app = Flask(__name__)

csp = {
    'default-src': [
        '\'self\'',
    ],
    'script-src': [
        '\'self\'',
        '\'unsafe-inline\'',      # autorise les scripts inline (comme vos <script>)
        'https://cdn.jsdelivr.net',
        'https://unpkg.com',
    ],
    'style-src': [
        '\'self\'',
        '\'unsafe-inline\'',      # autorise les styles inline (vos style="...")
        'https://cdn.jsdelivr.net',
        'https://fonts.googleapis.com',
        'https://unpkg.com',
    ],
    'font-src': [
        '\'self\'',
        'https://cdn.jsdelivr.net',
        'https://fonts.gstatic.com',
    ],
    'img-src': [
        '\'self\'',
        'data:',
        'https://via.placeholder.com',
    ],
    'connect-src': [
        '\'self\'',
    ],
}

Talisman(app, content_security_policy=csp, force_https=False)

# Configuration du serveur de messagerie (depuis .env)
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 465))
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'True').lower() == 'true'
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')


mail = Mail(app)

# Clé secrète pour les sessions (indispensable)
app.secret_key = os.getenv('SECRET_KEY')

app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_SECRET_KEY'] = app.secret_key  # optionnel, utilise la même clé
csrf = CSRFProtect(app)

# Configuration de la base de données SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///commandes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialisation de SQLAlchemy avec l'application
db.init_app(app)

# Import du modèle APRÈS l'initialisation de db
from models import Commande, Admin, Produit


# Route pour la page d'accueil
@app.route('/')
def index():
    produit = Produit.query.first()
    return render_template('landing.html', produit=produit, active_page='index')

# Route pour traiter la commande

@app.route('/produit')
def produit():
    produit = Produit.query.first()
    return render_template('produit.html', produit=produit, active_page='produit')

@app.route('/commander')
def commander_page():
    produit = Produit.query.first()
    return render_template('commande.html', produit=produit)

@app.route('/commander', methods=['POST'])
def commander():
    # Récupération des données du formulaire
    nom = request.form['nom']
    prenom = request.form['prenom']
    adresse = request.form['adresse']
    telephone = request.form['telephone']
    quantite = request.form['quantite']
    email = request.form['email']

    # Validations
    erreurs = []
    if not nom or not prenom:
        erreurs.append("Le nom et le prénom sont obligatoires.")
    if not email or '@' not in email:
        erreurs.append("Email invalide.")
    if not telephone or not telephone.isdigit() or len(telephone) < 10:
        erreurs.append("Téléphone invalide (10 chiffres minimum).")
    if not adresse or len(adresse) < 10:
        erreurs.append("Adresse trop courte.")
    try:
        quantite = int(quantite)
        if quantite < 1 or quantite > 10:
            erreurs.append("Quantité doit être entre 1 et 10.")
    except ValueError:
        erreurs.append("Quantité invalide.")

    if erreurs:
        for err in erreurs:
            flash(err, 'danger')
        return redirect(url_for('commander_page'))

    produit = Produit.query.first()
    if produit.stock < quantite:
        flash("Désolé, stock insuffisant.", 'danger')
        return redirect(url_for('commander_page'))

    # Sinon, on crée la commande et on décrémente
    produit.stock -= quantite
    # Sinon, on crée la commande
    # Création d'un objet Commande
    nouvelle_commande = Commande(
        nom=nom,
        prenom=prenom,
        email=email,
        adresse=adresse,
        telephone=telephone,
        quantite=quantite,
        statut='en attente'
    )

    # Ajout à la base de données
    db.session.add(nouvelle_commande)
    db.session.flush()  # permet d'obtenir l'ID sans commit

    # Génération du numéro : CMD-année-000ID
    nouvelle_commande.numero = f"CMD-{datetime.now().year}-{nouvelle_commande.id:04d}"
    db.session.commit()
    send_confirmation_email(nouvelle_commande)
    send_notification_admin(nouvelle_commande)

    flash('Commande enregistrée avec succès !', 'success')
    # Redirection vers la page de confirmation
    return redirect(url_for('confirmation', commande_id=nouvelle_commande.id))


def send_confirmation_email(commande):
    try:
        # Générer les versions HTML et texte à partir des templates
        html_body = render_template('emails/confirmation_email.html', commande=commande)
        text_body = render_template('emails/confirmation_email.txt', commande=commande)

        msg = Message(
            subject=f"Confirmation de commande n°{commande.id} - Dulcibelle",
            recipients=[commande.email],
            html=html_body,
            body=text_body
        )
        mail.send(msg)
        app.logger.info(f"Email de confirmation envoyé à {commande.email}")
    except Exception as e:
        app.logger.error(f"Erreur envoi email confirmation : {e}")

def send_notification_admin(commande):
    try:
        admin_email = os.getenv('ADMIN_EMAIL')
        if not admin_email:
            app.logger.error("ADMIN_EMAIL non défini dans les variables d'environnement")
            return
        msg = Message(
            subject=f"Nouvelle commande n°{commande.id} - Dulcibelle",
            recipients=[admin_email]
        )
        msg.body = f"""
        Nouvelle commande reçue :\n
        Client : {commande.prenom} {commande.nom}\n
        Téléphone : {commande.telephone}\n
        Adresse : {commande.adresse}\n
        Quantité : {commande.quantite}\n
        """
        mail.send(msg)
    except Exception as e:
        app.logger.error(f"Erreur envoi email admin : {e}")

# Route de confirmation
@app.route('/confirmation/<int:commande_id>')
def confirmation(commande_id):
    commande = Commande.query.get_or_404(commande_id)
    return render_template('confirmation.html', commande=commande)

@app.route('/histoire')
def histoire():
    return render_template('histoire.html', active_page='histoire')

@app.route('/contact')
def contact():
    return render_template('contact.html', active_page='contact')

# Routes pour les pages légales
@app.route('/mentions-legales')
def mentions():
    return render_template('mentions.html')

@app.route('/cgv')
def cgv():
    return render_template('cgv.html', active_page='cgv')

@app.route('/faq')
def faq():
    return render_template('faq.html', active_page='faq')


# Décorateur pour protéger les routes admin
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Veuillez vous connecter pour accéder à cette page.', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            session['admin_logged_in'] = True
            flash('Connexion réussie.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Identifiants incorrects.', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Vous êtes déconnecté.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    # Pagination simple (10 commandes par page)
    page = request.args.get('page', 1, type=int)
    commandes = Commande.query.order_by(Commande.date_commande.desc()).paginate(page=page, per_page=10)
    return render_template('admin_dashboard.html', commandes=commandes)

@app.route('/admin/commande/<int:id>')
@login_required
def admin_commande_detail(id):
    commande = Commande.query.get_or_404(id)
    return render_template('admin_commande_detail.html', commande=commande)

@app.route('/admin/commande/<int:id>/statut', methods=['POST'])
@login_required
def admin_changer_statut(id):
    commande = Commande.query.get_or_404(id)
    nouveau_statut = request.form['statut']
    if nouveau_statut in ['en attente', 'expédiée', 'annulée']:
        commande.statut = nouveau_statut
        db.session.commit()
        flash('Statut mis à jour.', 'success')
    else:
        flash('Statut invalide.', 'danger')
    return redirect(url_for('admin_commande_detail', id=id))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.route('/debug-templates')
def debug_templates():
    template_dir = os.path.join(app.root_path, 'templates')
    if os.path.exists(template_dir):
        files = os.listdir(template_dir)
        return f"Fichiers dans templates : {files}"
    else:
        return "Le dossier templates n'existe pas !"

@app.route('/debug-mail-config')
def debug_mail_config():
    config = {
        'MAIL_SERVER': app.config.get('MAIL_SERVER'),
        'MAIL_PORT': app.config.get('MAIL_PORT'),
        'MAIL_USE_SSL': app.config.get('MAIL_USE_SSL'),
        'MAIL_USE_TLS': app.config.get('MAIL_USE_TLS'),
        'MAIL_USERNAME': app.config.get('MAIL_USERNAME'),
        'MAIL_DEFAULT_SENDER': app.config.get('MAIL_DEFAULT_SENDER'),
    }
    return str(config)

@app.errorhandler(400)
def csrf_error(error):
    flash('Le formulaire a expiré ou est invalide. Veuillez réessayer.', 'danger')
    return redirect(request.referrer or url_for('index'))

# Lancement de l'application
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Créer le produit par défaut s'il n'existe pas
        if Produit.query.count() == 0:
            p = Produit(stock=100)
            db.session.add(p)
            db.session.commit()
    app.run(host="0.0.0.0", port=5000, debug=True)