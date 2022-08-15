from sqlalchemy.dialects.postgresql import JSON
from . import db

class Tallying(db.Model):
    __tablename__ = "Tallying"


    '''
    CREATE TABLE Tallying(
   id INT PRIMARY KEY     NOT NULL,
   polling_station   TEXT,
   raila         CHAR(50),
   wajackoyah   CHAR(50),
   ruto         CHAR(50),
   mwaure       CHAR(50),
);
    '''


    id = db.Column(db.Integer, primary_key=True)
    polling_station = db.Column(db.String(128), unique=True, nullable=False)
    raila = db.Column(db.String(128), nullable=True)
    ruto = db.Column(db.String(128), nullable=True)
    wajackoyah = db.Column(db.String(128), nullable=True)
    mwaure = db.Column(db.String(128), nullable=True)

    def __str__(self):
        return self.polling_station

    def serialize(self):
        return {"id": self.id,
                "polling_station": self.polling_station,
                "ruto": self.ruto,
                "mwaure": self.mwaure,
                "raila": self.raila,
                "wajackoyah": self.wajackoyah}