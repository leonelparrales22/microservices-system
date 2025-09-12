import React, { useState } from 'react';
import './AddTask.css';

/**
 * AddTask Component
 * 
 * Provides an input form for adding new tasks to the to-do list.
 * Includes validation and keyboard shortcuts for better user experience.
 * 
 * @param {Function} onAddTask - Function to handle adding a new task
 * @returns {JSX.Element} The add task component
 */
const AddTask = ({ onAddTask }) => {
  // State for managing the input text
  const [taskText, setTaskText] = useState('');
  
  // State for managing input validation
  const [isValid, setIsValid] = useState(true);

  /**
   * Handle form submission
   * @param {Event} e - The form submit event
   */
  const handleSubmit = (e) => {
    e.preventDefault();
    
    const trimmedText = taskText.trim();
    
    // Validate input
    if (trimmedText === '') {
      setIsValid(false);
      return;
    }

    // Add the task and reset form
    onAddTask(trimmedText);
    setTaskText('');
    setIsValid(true);
  };

  /**
   * Handle input text change
   * @param {Event} e - The input change event
   */
  const handleInputChange = (e) => {
    const value = e.target.value;
    setTaskText(value);
    
    // Reset validation state when user starts typing
    if (!isValid && value.trim() !== '') {
      setIsValid(true);
    }
  };

  /**
   * Handle key press events
   * @param {KeyboardEvent} e - The keyboard event
   */
  const handleKeyPress = (e) => {
    // Clear validation error on any key press
    if (!isValid) {
      setIsValid(true);
    }
  };

  return (
    <div className="add-task">
      <form onSubmit={handleSubmit} className="add-task-form">
        <div className="input-group">
          <input
            type="text"
            value={taskText}
            onChange={handleInputChange}
            onKeyDown={handleKeyPress}
            placeholder="Enter a new task..."
            className={`task-input ${!isValid ? 'invalid' : ''}`}
            maxLength={500}
            autoComplete="off"
          />
          <button
            type="submit"
            className="add-btn"
            disabled={taskText.trim() === ''}
            title="Add task (Enter)"
          >
            Add Task
          </button>
        </div>
        
        {/* Validation error message */}
        {!isValid && (
          <div className="error-message">
            Please enter a valid task description.
          </div>
        )}
        
        {/* Character count indicator */}
        <div className="input-meta">
          <span className="char-count">
            {taskText.length}/500 characters
          </span>
          <span className="keyboard-hint">
            Press Enter to add task
          </span>
        </div>
      </form>
    </div>
  );
};

export default AddTask;