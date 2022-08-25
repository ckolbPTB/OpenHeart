from openheart import db

class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(384), unique=False, nullable=False)

    def __repr__(self):
        return f'<Email: {self.email}>'
