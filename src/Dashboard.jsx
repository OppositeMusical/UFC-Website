import React, { useState, useEffect } from 'react';
import { LogOut, Key, Save } from 'lucide-react';
import { signOut } from 'firebase/auth';
import { doc, getDoc, updateDoc } from 'firebase/firestore';
import { auth, db } from './firebase';

export default function Dashboard({ user }) {
  const [userData, setUserData] = useState(null);
  const [provider, setProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState({ text: '', type: '' });

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const userDocRef = doc(db, 'users', user.uid);
        const userDocSnap = await getDoc(userDocRef);
        if (userDocSnap.exists()) {
          setUserData(userDocSnap.data());
        }
      } catch (error) {
        console.error("Error fetching user data:", error);
      }
    };
    fetchUserData();
  }, [user]);

  const handleLogout = async () => {
    try {
      await signOut(auth);
    } catch (error) {
      console.error("Error signing out: ", error);
    }
  };

  const handleSaveKey = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setMessage({ text: '', type: '' });

    try {
      const userDocRef = doc(db, 'users', user.uid);
      await updateDoc(userDocRef, {
        [`apiKeys.${provider}`]: apiKey
      });
      
      // Update local state to reflect changes without re-fetching
      setUserData(prev => ({
        ...prev,
        apiKeys: {
          ...prev?.apiKeys,
          [provider]: apiKey
        }
      }));
      
      setMessage({ text: 'API Key saved successfully!', type: 'success' });
      setApiKey(''); // clear input
    } catch (error) {
      setMessage({ text: error.message, type: 'error' });
    } finally {
      setIsSaving(false);
    }
  };

  const getProviderName = (key) => {
    switch (key) {
      case 'openai': return 'ChatGPT (OpenAI)';
      case 'anthropic': return 'Claude (Anthropic)';
      case 'gemini': return 'Google Gemini';
      case 'deepseek': return 'DeepSeek';
      default: return key;
    }
  };

  return (
    <div className="login-container" style={{ maxWidth: '600px' }}>
      <div className="login-header" style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ textAlign: 'left', fontSize: '1.5rem' }}>
            Welcome, {userData ? userData.firstName : '...'}!
          </h1>
          <p style={{ textAlign: 'left' }}>Manage your API keys securely.</p>
        </div>
        <button 
          onClick={handleLogout} 
          style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
          title="Log out"
        >
          <LogOut size={24} />
        </button>
      </div>

      <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1.5rem', borderRadius: '16px', marginTop: '2rem' }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem', fontWeight: 600 }}>Add New API Key</h2>
        
        {message.text && (
          <div style={{ color: message.type === 'error' ? '#ff6b6b' : '#4ade80', marginBottom: '1rem', fontSize: '0.875rem' }}>
            {message.text}
          </div>
        )}

        <form onSubmit={handleSaveKey}>
          <div className="form-group">
            <label htmlFor="provider">Select Provider</label>
            <select
              id="provider"
              className="form-input"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              style={{ appearance: 'none', paddingLeft: '1rem' }}
            >
              <option value="openai">ChatGPT (OpenAI)</option>
              <option value="anthropic">Claude (Anthropic)</option>
              <option value="gemini">Google Gemini</option>
              <option value="deepseek">DeepSeek</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="apiKey">API Key</label>
            <div className="input-wrapper">
              <Key className="input-icon" />
              <input
                id="apiKey"
                type="password"
                className="form-input"
                placeholder="sk-..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                required
              />
            </div>
          </div>

          <button type="submit" className="login-button" disabled={isSaving || !apiKey}>
            {isSaving ? <span>Saving...</span> : <><Save size={20} /><span>Save Key</span></>}
          </button>
        </form>
      </div>

      {userData?.apiKeys && Object.keys(userData.apiKeys).length > 0 && (
        <div style={{ marginTop: '2rem' }}>
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Stored Keys
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {Object.keys(userData.apiKeys).map((key) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '1rem', background: 'var(--surface-border)', borderRadius: '8px' }}>
                <span style={{ fontWeight: 500 }}>{getProviderName(key)}</span>
                <span style={{ color: '#4ade80', fontSize: '0.875rem' }}>✓ Configured</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
