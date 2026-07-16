import React, { useState, useEffect } from 'react';
import './index.css'; // Ensure global styles are loaded
import Login from './Login';
import Signup from './Signup';
import Dashboard from './Dashboard';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from './firebase';

function App() {
  const [currentView, setCurrentView] = useState('login'); // 'login' or 'signup'
  const [user, setUser] = useState(null);
  const [isInitializing, setIsInitializing] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setIsInitializing(false);
    });

    return () => unsubscribe();
  }, []);

  if (isInitializing) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <div style={{ color: 'var(--primary)', fontSize: '1.25rem', fontWeight: 600 }}>Loading...</div>
      </div>
    );
  }

  return (
    <>
      <div className="bg-orb orb-1"></div>
      <div className="bg-orb orb-2"></div>
      
      {user ? (
        <Dashboard user={user} />
      ) : (
        currentView === 'login' ? (
          <Login onSwitchToSignup={() => setCurrentView('signup')} />
        ) : (
          <Signup onSwitchToLogin={() => setCurrentView('login')} />
        )
      )}
    </>
  );
}

export default App;
