import os
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash, current_app
from werkzeug.utils import secure_filename
from config import Config
from .forms import ResumeUploadForm, ChatForm
from agents.supervisor import JobAssistantSupervisor
from app.services.chat_agent import ChatAgent
import logging
import json
from datetime import datetime
import time


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

# Initialize job assistant
job_assistant = JobAssistantSupervisor()

def store_resume_data(filepath, resume_insights):
    """Store both resume path and insights in session"""
    session['uploaded_resume_path'] = filepath
    # Store insights as JSON string to ensure it's serializable
    session['resume_insights'] = json.dumps(resume_insights)
    logger.info(f"Stored resume data in session: {filepath}")

def get_resume_data():
    """Retrieve resume path and insights from session"""
    filepath = session.get('resume_path')
    insights_json = session.get('resume_insights')
    insights = json.loads(insights_json) if insights_json else None
    return filepath, insights


@main_bp.route('/', methods=['GET', 'POST'])
def index():
    upload_form = ResumeUploadForm()
    chat_form = ChatForm()

    if upload_form.validate_on_submit():
        return handle_resume_upload(upload_form.resume.data)

    return render_template('index.html', upload_form=upload_form, chat_form=chat_form)


@main_bp.route('/upload_resume', methods=['POST'])
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({'success': False, 'error': 'No resume file provided.'})
    
    file = request.files['resume']
    return handle_resume_upload(file)


def handle_resume_upload(file):
    """Centralized resume upload handling"""
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file.'}) if request.is_json else redirect(url_for('main.index'))
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    try:
        # Ensure upload directory exists
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Save the file
        file.save(filepath)
        logger.info(f"Resume uploaded: {filepath}")
        
        # Consistent session storage
        session['resume_path'] = filepath
        
        # Analyze resume
        resume_insights = job_assistant.set_resume(filepath)
        
        # Store insights
        session['resume_insights'] = json.dumps(resume_insights)
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Resume uploaded successfully'
            })
        else:
            flash('Resume uploaded successfully!', 'success')
            return redirect(url_for('main.chat_interface'))
    
    except Exception as e:
        logger.error(f"Resume upload error: {str(e)}")
        if request.is_json:
            return jsonify({
                'success': False,
                'error': str(e)
            })
        else:
            flash('An error occurred during upload. Please try again.', 'danger')
            return redirect(url_for('main.index'))
        

@main_bp.route('/chat', methods=['GET'])
def chat_interface():
    """Render the chat interface."""
    filepath, resume_insights = get_resume_data()

    if not filepath or not os.path.exists(filepath):
        logger.error("Resume file not found in session or missing on disk.")
        flash("Please upload your resume to proceed.", "warning")
        session.clear()  # Clear invalid session data
        return redirect(url_for('main.index'))

    chat_form = ChatForm()
    return render_template(
        'chat_interface.html',
        chat_form=chat_form,
        resume_insights=resume_insights
    )



@main_bp.route('/check_analysis_status')
def check_analysis_status():
    """Check the status of resume analysis"""
    try:
        filepath = session.get('resume_filepath')
        if not filepath:
            return jsonify({
                'success': False,
                'error': 'No resume found in session'
            })
            
        # Check if analysis results exist
        insights_json = session.get('resume_insights')
        if insights_json:
            return jsonify({
                'success': True,
                'message': 'Analysis complete'
            })
            
        # If analysis has been running too long (over 30 seconds)
        start_time = session.get('analysis_started', 0)
        if time.time() - start_time > 30:
            return jsonify({
                'success': False,
                'error': 'Analysis timeout'
            })
            
        return jsonify({
            'success': False,
            'message': 'Analysis in progress'
        })
        
    except Exception as e:
        logger.error(f"Analysis status check error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })
    


@main_bp.route('/chat/message', methods=["POST"])
def chat_message():
    """Handle chat interactions."""
    chat_form = ChatForm()

    if chat_form.validate_on_submit():
        try:
            filepath, resume_insights = get_resume_data()
            if not filepath:
                raise ValueError("No resume loaded. Please upload your resume first.")

            query = chat_form.query.data
            
            # Use job assistant with current resume
            response_data = job_assistant.process_query(query)

            return jsonify({
                "response": response_data.get("response"),
                "intent": response_data.get("intent"),
                "agent": response_data.get("agent"),
                "error": response_data.get("error")
            })
        
        except Exception as e:
            logger.error(f"Chat message processing error: {str(e)}")
            return jsonify({
                'error': str(e),
                'response': "An error occurred while processing your request.",
                'intent': 'error',
                'agent': None
            }), 500

    return jsonify({'error': 'Invalid form submission'}), 400


