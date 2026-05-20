from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import pdfkit
import os

db = SQLAlchemy()
login_manager = LoginManager()

# Configuração robusta do PDFKit
path_wkhtmltopdf = os.environ.get('WKHTMLTOPDF_PATH', '/usr/bin/wkhtmltopdf')

# Tentamos configurar, se falhar, definimos como None
try:
    pdf_config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
    print("PDFKit configurado com sucesso.")
except OSError:
    pdf_config = None
    print("Aviso: wkhtmltopdf não encontrado. Exportação PDF desativada.")

pdf_options = {
    'page-size': 'A4',
    'encoding': "UTF-8",
    'no-outline': None
}