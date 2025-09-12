import React, { useState, useEffect } from 'react';
import './App.css';
import TaskList from './components/TaskList';
import AddTask from './components/AddTask';

/**
 * Main To-Do List Application Component
 * 
 * Features:
 * - Add new tasks
 * - Edit existing tasks
 * - Delete tasks
 * - Mark tasks as completed
 * - Persist data in localStorage
 * 
 * @returns {JSX.Element} The main application component
 */
function App() {
  // State for managing the list of tasks
  const [tasks, setTasks] = useState([]);

  // Load tasks from localStorage on component mount
  useEffect(() => {
    const savedTasks = localStorage.getItem('todoTasks');
    if (savedTasks) {
      try {
        setTasks(JSON.parse(savedTasks));
      } catch (error) {
        console.error('Error loading tasks from localStorage:', error);
        setTasks([]);
      }
    }
  }, []);

  // Save tasks to localStorage whenever tasks change
  useEffect(() => {
    localStorage.setItem('todoTasks', JSON.stringify(tasks));
  }, [tasks]);

  /**
   * Add a new task to the list
   * @param {string} taskText - The text content of the new task
   */
  const addTask = (taskText) => {
    if (taskText.trim() === '') return;
    
    const newTask = {
      id: Date.now(), // Simple ID generation using timestamp
      text: taskText.trim(),
      completed: false,
      createdAt: new Date().toISOString()
    };
    
    setTasks(prevTasks => [...prevTasks, newTask]);
  };

  /**
   * Edit an existing task
   * @param {number} taskId - The ID of the task to edit
   * @param {string} newText - The new text content for the task
   */
  const editTask = (taskId, newText) => {
    if (newText.trim() === '') return;
    
    setTasks(prevTasks =>
      prevTasks.map(task =>
        task.id === taskId
          ? { ...task, text: newText.trim(), updatedAt: new Date().toISOString() }
          : task
      )
    );
  };

  /**
   * Delete a task from the list
   * @param {number} taskId - The ID of the task to delete
   */
  const deleteTask = (taskId) => {
    setTasks(prevTasks => prevTasks.filter(task => task.id !== taskId));
  };

  /**
   * Toggle the completion status of a task
   * @param {number} taskId - The ID of the task to toggle
   */
  const toggleTaskCompletion = (taskId) => {
    setTasks(prevTasks =>
      prevTasks.map(task =>
        task.id === taskId
          ? { ...task, completed: !task.completed, updatedAt: new Date().toISOString() }
          : task
      )
    );
  };

  /**
   * Clear all completed tasks
   */
  const clearCompleted = () => {
    setTasks(prevTasks => prevTasks.filter(task => !task.completed));
  };

  // Calculate task statistics
  const totalTasks = tasks.length;
  const completedTasks = tasks.filter(task => task.completed).length;
  const pendingTasks = totalTasks - completedTasks;

  return (
    <div className="App">
      <header className="App-header">
        <h1>To-Do List Application</h1>
        <p>Manage your tasks efficiently with persistent local storage</p>
      </header>

      <main className="App-main">
        <div className="todo-container">
          {/* Task statistics */}
          <div className="task-stats">
            <span className="stat-item">Total: {totalTasks}</span>
            <span className="stat-item">Pending: {pendingTasks}</span>
            <span className="stat-item">Completed: {completedTasks}</span>
          </div>

          {/* Add new task form */}
          <AddTask onAddTask={addTask} />

          {/* Task list */}
          <TaskList
            tasks={tasks}
            onEditTask={editTask}
            onDeleteTask={deleteTask}
            onToggleCompletion={toggleTaskCompletion}
          />

          {/* Clear completed tasks button */}
          {completedTasks > 0 && (
            <div className="task-actions">
              <button
                className="clear-completed-btn"
                onClick={clearCompleted}
                title="Remove all completed tasks"
              >
                Clear Completed ({completedTasks})
              </button>
            </div>
          )}

          {/* Empty state message */}
          {totalTasks === 0 && (
            <div className="empty-state">
              <p>No tasks yet. Add your first task above!</p>
            </div>
          )}
        </div>
      </main>

      <footer className="App-footer">
        <p>
          Data is automatically saved to your browser's local storage.
          Tasks will persist across page reloads.
        </p>
      </footer>
    </div>
  );
}

export default App;
