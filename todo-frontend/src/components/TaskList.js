import React from 'react';
import TaskItem from './TaskItem';
import './TaskList.css';

/**
 * TaskList Component
 * 
 * Renders the list of tasks with filtering and sorting capabilities.
 * Each task is rendered using the TaskItem component.
 * 
 * @param {Array} tasks - Array of task objects
 * @param {Function} onEditTask - Function to handle task editing
 * @param {Function} onDeleteTask - Function to handle task deletion
 * @param {Function} onToggleCompletion - Function to handle task completion toggle
 * @returns {JSX.Element} The task list component
 */
const TaskList = ({ tasks, onEditTask, onDeleteTask, onToggleCompletion }) => {
  // Separate tasks into pending and completed for better organization
  const pendingTasks = tasks.filter(task => !task.completed);
  const completedTasks = tasks.filter(task => task.completed);

  return (
    <div className="task-list">
      {/* Pending Tasks Section */}
      {pendingTasks.length > 0 && (
        <div className="task-section">
          <h3 className="section-title">
            Pending Tasks ({pendingTasks.length})
          </h3>
          <div className="tasks-container">
            {pendingTasks.map(task => (
              <TaskItem
                key={task.id}
                task={task}
                onEdit={onEditTask}
                onDelete={onDeleteTask}
                onToggleCompletion={onToggleCompletion}
              />
            ))}
          </div>
        </div>
      )}

      {/* Completed Tasks Section */}
      {completedTasks.length > 0 && (
        <div className="task-section">
          <h3 className="section-title">
            Completed Tasks ({completedTasks.length})
          </h3>
          <div className="tasks-container">
            {completedTasks.map(task => (
              <TaskItem
                key={task.id}
                task={task}
                onEdit={onEditTask}
                onDelete={onDeleteTask}
                onToggleCompletion={onToggleCompletion}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default TaskList;