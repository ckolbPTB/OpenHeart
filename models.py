from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager
 
login = LoginManager()
db = SQLAlchemy()
 
class UserModel(UserMixin, db.Model):
    __tablename__ = 'users'
 
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    token_hash = db.Column(db.String())
 
    def set_token(self, token):
        self.token_hash = generate_password_hash(token)
     
    def check_token(self, token):
        return check_password_hash(self.token_hash, token)
 
 
@login.user_loader
def load_user(id):
    return UserModel.query.get(int(id))
