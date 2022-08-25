from flask import (
    Blueprint, render_template)

from flask_login import login_required

from openheart.utils.utils import clean_up_user_files

bp = Blueprint('upload', __name__, url_prefix='/upload')


@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    clean_up_user_files()
    return render_template('upload/upload.html')