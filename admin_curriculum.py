"""Admin dashboard routes for curriculum management."""

from flask import Blueprint, render_template, jsonify, request
from curriculum_db import get_curriculum, get_curriculum_stats, get_db_connection, insert_curriculum
import json

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/curriculum', methods=['GET'])
def curriculum_dashboard():
    """Admin dashboard for curriculum management."""
    all_curriculum = get_curriculum()
    stats = get_curriculum_stats()
    
    # Sort by subject and grade
    all_curriculum.sort(key=lambda x: (x.get('subject', ''), x.get('grade', '')))
    
    return render_template('admin/curriculum_dashboard.html', 
                         curriculum=all_curriculum,
                         stats=stats)


@admin_bp.route('/curriculum/api/all', methods=['GET'])
def get_all_curriculum():
    """API endpoint to get all curriculum data."""
    all_curriculum = get_curriculum()
    return jsonify({
        'success': True,
        'data': all_curriculum,
        'stats': get_curriculum_stats(),
    })


@admin_bp.route('/curriculum/api/<int:curriculum_id>', methods=['GET'])
def get_curriculum_detail(curriculum_id):
    """API endpoint to get single curriculum entry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM curriculum WHERE id = ?", (curriculum_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    
    row_dict = dict(row)
    data = {
        'id': row_dict.get('id'),
        'subject': row_dict.get('subject', ''),
        'grade': row_dict.get('grade', ''),
        'strand': row_dict.get('strand', ''),
        'substrand': row_dict.get('substrand', ''),
        'learning_outcomes': json.loads(row_dict.get('learning_outcomes') or '[]'),
        'key_inquiry_questions': json.loads(row_dict.get('key_inquiry') or '[]'),
        'suggested_learning_experiences': json.loads(row_dict.get('activities') or '[]'),
        'core_competencies': json.loads(row_dict.get('competencies') or '[]'),
        'values': json.loads(row_dict.get('values_') or '[]'),
        'notes': row_dict.get('raw_text', ''),
    }
    
    return jsonify({'success': True, 'data': data})


@admin_bp.route('/curriculum/api/<int:curriculum_id>', methods=['POST'])
def update_curriculum(curriculum_id):
    """API endpoint to update curriculum entry."""
    data = request.get_json()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build update query - map frontend field names to DB column names
    field_mapping = {
        'strand': 'strand',
        'substrand': 'substrand',
        'learning_outcomes': 'learning_outcomes',
        'key_inquiry_questions': 'key_inquiry',
        'suggested_learning_experiences': 'activities',
        'core_competencies': 'competencies',
        'values': 'values_',
        'notes': 'raw_text',
    }
    
    updates = []
    params = []
    
    for frontend_field, db_field in field_mapping.items():
        if frontend_field in data:
            val = data[frontend_field]
            # JSON encode list fields
            if isinstance(val, list):
                val = json.dumps(val)
            updates.append(f"{db_field} = ?")
            params.append(val)
    
    if updates:
        params.append(curriculum_id)
        query = f"UPDATE curriculum SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
    
    conn.close()
    
    return jsonify({
        'success': True, 
        'message': 'Updated successfully',
    })


@admin_bp.route('/curriculum/stats', methods=['GET'])
def curriculum_stats():
    """Get curriculum statistics."""
    return jsonify(get_curriculum_stats())
