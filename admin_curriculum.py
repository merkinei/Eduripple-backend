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
    
    # Sort by completeness score (lowest first - needs review)
    all_curriculum.sort(key=lambda x: x['completeness_score'])
    
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
    
    data = {
        'id': row['id'],
        'subject': row['subject'],
        'grade': row['grade'],
        'strand': row['strand'],
        'substrand': row['substrand'],
        'learning_outcomes': json.loads(row['learning_outcomes'] or '[]'),
        'key_inquiry_questions': json.loads(row['key_inquiry_questions'] or '[]'),
        'suggested_learning_experiences': json.loads(row['suggested_learning_experiences'] or '[]'),
        'core_competencies': json.loads(row['core_competencies'] or '[]'),
        'values': json.loads(row['curriculum_values'] or '[]'),
        'status': row['status'],
        'completeness_score': row['completeness_score'],
        'notes': row['notes'],
    }
    
    return jsonify({'success': True, 'data': data})


@admin_bp.route('/curriculum/api/<int:curriculum_id>', methods=['POST'])
def update_curriculum(curriculum_id):
    """API endpoint to update curriculum entry."""
    data = request.get_json()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build update query
    updates = []
    params = []
    
    for field in ['strand', 'substrand', 'status', 'notes']:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])
    
    for field in ['learning_outcomes', 'key_inquiry_questions', 
                  'suggested_learning_experiences', 'core_competencies', 'values']:
        if field in data:
            db_field = 'curriculum_values' if field == 'values' else field
            updates.append(f"{db_field} = ?")
            params.append(json.dumps(data[field]))
    
    if updates:
        updates.append("last_updated = CURRENT_TIMESTAMP")
        params.append(curriculum_id)
        
        query = f"UPDATE curriculum SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
    
    conn.close()
    
    # Recalculate completeness
    updated = get_curriculum()
    updated_entry = next((c for c in updated if c['id'] == curriculum_id), None)
    
    return jsonify({
        'success': True, 
        'message': 'Updated successfully',
        'data': updated_entry,
    })


@admin_bp.route('/curriculum/stats', methods=['GET'])
def curriculum_stats():
    """Get curriculum statistics."""
    return jsonify(get_curriculum_stats())
