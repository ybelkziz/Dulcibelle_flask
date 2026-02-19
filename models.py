from extensions import db
from datetime import datetime

class Commande(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False)
    prenom = db.Column(db.String(50), nullable=False)
    adresse = db.Column(db.String(200), nullable=False)
    telephone = db.Column(db.String(20), nullable=False)
    quantite = db.Column(db.Integer, default=1)
    date_commande = db.Column(db.DateTime, default=datetime.utcnow)
    statut = db.Column(db.String(20), default='en attente')
    email = db.Column(db.String(100), nullable=False)
    numero = db.Column(db.String(20), unique=True)

    def __repr__(self):
        return f'<Commande {self.nom} {self.prenom}>'

class Produit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False, default="Sérum visage anti-tâches")
    prix = db.Column(db.Float, nullable=False, default=429)
    stock = db.Column(db.Integer, nullable=False, default=100)  # Stock initial
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(200), nullable=True)  # chemin relatif (ex: 'images/serum.jpg')
    ingredients = db.Column(db.Text, nullable=True)
    utilisation = db.Column(db.Text, nullable=True)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)