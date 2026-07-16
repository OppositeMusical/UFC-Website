import React, { useState } from 'react';
import { Mail, Lock, User, UserPlus } from 'lucide-react';
import { createUserWithEmailAndPassword } from 'firebase/auth';
import { doc, setDoc } from 'firebase/firestore';
import { auth, db } from './firebase';

export default function Signup({ onSwitchToLogin }) {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSignup = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    
    try {
      const userCredential = await createUserWithEmailAndPassword(auth, email, password);
      const user = userCredential.user;
      
      // Store extended user info in Firestore
      await setDoc(doc(db, 'users', user.uid), {
        firstName,
        lastName,
        email,
        createdAt: new Date().toISOString(),
        apiKeys: {}
      });
      
      // onAuthStateChanged in App.jsx will automatically route to Dashboard
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-header">
        <h1>Create Account</h1>
        <p>Sign up to get started</p>
      </div>

      {error && <div style={{ color: '#ff6b6b', marginBottom: '1rem', fontSize: '0.875rem', textAlign: 'center' }}>{error}</div>}

      <form onSubmit={handleSignup}>
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
          <div className="form-group" style={{ marginBottom: 0, flex: 1 }}>
            <label htmlFor="firstName">First Name</label>
            <div className="input-wrapper">
              <User className="input-icon" />
              <input
                id="firstName"
                type="text"
                className="form-input"
                placeholder="Jane"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 0, flex: 1 }}>
            <label htmlFor="lastName">Last Name</label>
            <div className="input-wrapper">
              <User className="input-icon" />
              <input
                id="lastName"
                type="text"
                className="form-input"
                placeholder="Doe"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                required
              />
            </div>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="email">Email</label>
          <div className="input-wrapper">
            <Mail className="input-icon" />
            <input
              id="email"
              type="email"
              className="form-input"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="form-group" style={{ marginBottom: '2rem' }}>
          <label htmlFor="password">Password</label>
          <div className="input-wrapper">
            <Lock className="input-icon" />
            <input
              id="password"
              type="password"
              className="form-input"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>
        </div>

        <button type="submit" className="login-button" disabled={isLoading}>
          {isLoading ? (
            <span>Creating account...</span>
          ) : (
            <>
              <UserPlus size={20} />
              <span>Sign Up</span>
            </>
          )}
        </button>
      </form>

      <div className="social-login">
        <p>Or sign up with</p>
        <div className="social-buttons">
          <button className="social-button" type="button" aria-label="Sign up with Github">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.03c3.18-.3 6.5-1.5 6.5-7.a4.6 4.6 0 0 0-1.3-3.2 4.08 4.08 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a11.9 11.9 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.08 4.08 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 5.5 3.3 6.7 6.5 7A4.8 4.8 0 0 0 9.5 18v4"></path></svg>
          </button>
          <button className="social-button" type="button" aria-label="Sign up with Twitter">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5 2.8 12.7 3 11c-1.1 0-2-.4-2-.4s1.7-2.7 3.3-3C2.1 6.1 2.3 3.4 2.3 3.4s2.6 1.7 4.7 2C7.5 1.5 11 1.7 12 4.5c1-.9 2.1-1.3 3-1.3 1.9 0 3 1.4 3 1.4"></path></svg>
          </button>
        </div>
      </div>

      <div className="signup-link">
        Already have an account?{' '}
        <a href="#" onClick={(e) => { e.preventDefault(); onSwitchToLogin(); }}>
          Log in
        </a>
      </div>
    </div>
  );
}
