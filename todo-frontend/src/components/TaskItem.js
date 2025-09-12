import React, { useState } from 'react';
import './TaskItem.css';

/**
 * TaskItem Component
 * 
 * Represents a single task in the to-do list with inline editing capabilities.
 * Provides controls for completing, editing, and deleting tasks.
 * 
 * @param {Object} task - The task object containing id, text, completed status
 * @param {Function} onEdit - Function to handle task editing
 * @param {Function} onDelete - Function to handle task deletion
 * @param {Function} onToggleCompletion - Function to handle task completion toggle
 * @returns {JSX.Element} The task item component
 */
const TaskItem = ({ task, onEdit, onDelete, onToggleCompletion }) => {
  // State for managing edit mode
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(task.text);

  /**
   * Handle saving the edited task
   */
  const handleSave = () => {
    if (editText.trim()) {
      onEdit(task.id, editText);
      setIsEditing(false);
    } else {
      // Reset to original text if empty
      setEditText(task.text);
      setIsEditing(false);
    }
  };

  /**
   * Handle canceling the edit
   */
  const handleCancel = () => {
    setEditText(task.text);
    setIsEditing(false);
  };

  /**
   * Handle key press events in edit mode
   * @param {KeyboardEvent} e - The keyboard event
   */
  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  /**
   * Format the task creation/update date
   * @param {string} dateString - ISO date string
   * @returns {string} Formatted date
   */
  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  return (
    <div className={`task-item ${task.completed ? 'completed' : ''}`}>
      {/* Task completion checkbox */}
      <label className="checkbox-container">
        <input
          type="checkbox"
          checked={task.completed}
          onChange={() => onToggleCompletion(task.id)}
          className="task-checkbox"
        />
        <span className="checkmark"></span>
      </label>

      {/* Task content area */}
      <div className="task-content">
        {isEditing ? (
          /* Edit mode */
          <div className="edit-mode">
            <input
              type="text"
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              onKeyDown={handleKeyPress}
              onBlur={handleSave}
              className="edit-input"
              autoFocus
              placeholder="Enter task description..."
            />
            <div className="edit-actions">
              <button
                onClick={handleSave}
                className="save-btn"
                title="Save changes (Enter)"
              >
                ✓
              </button>
              <button
                onClick={handleCancel}
                className="cancel-btn"
                title="Cancel edit (Escape)"
              >
                ✕
              </button>
            </div>
          </div>
        ) : (
          /* View mode */
          <div className="view-mode">
            <span className="task-text" title={task.text}>
              {task.text}
            </span>
            <div className="task-meta">
              {task.createdAt && (
                <span className="task-date">
                  Created: {formatDate(task.createdAt)}
                </span>
              )}
              {task.updatedAt && task.updatedAt !== task.createdAt && (
                <span className="task-date">
                  Updated: {formatDate(task.updatedAt)}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Task action buttons */}
      {!isEditing && (
        <div className="task-actions">
          <button
            onClick={() => setIsEditing(true)}
            className="edit-btn"
            title="Edit task"
            disabled={task.completed}
          >
            ✏️
          </button>
          <button
            onClick={() => onDelete(task.id)}
            className="delete-btn"
            title="Delete task"
          >
            🗑️
          </button>
        </div>
      )}
    </div>
  );
};

export default TaskItem;