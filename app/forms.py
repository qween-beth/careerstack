from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired

class ResumeUploadForm(FlaskForm):
    """Form for uploading resume"""
    resume = FileField(
        'Upload Resume', 
        validators=[
            FileRequired(),
            FileAllowed(['pdf'], 'PDF files only!')
        ]
    )
    submit = SubmitField('Upload Resume')

class ChatForm(FlaskForm):
    """Form for chat interface"""
    query = StringField('Query', validators=[DataRequired()])
    submit = SubmitField('Send')