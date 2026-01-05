import React from 'react';

const StrategyControls = ({ isTrading, onStart, onStop }) => {
  return (
    <div style={{ 
      display: 'flex', 
      gap: '1rem', 
      alignItems: 'center',
      padding: '1rem',
      background: 'rgba(100, 200, 255, 0.05)',
      borderRadius: '12px',
      border: '1px solid rgba(100, 200, 255, 0.1)'
    }}>
      <div style={{ marginRight: '1rem' }}>
        <div style={{ fontSize: '0.8rem', color: '#a0aec0', marginBottom: '0.3rem' }}>
          STRATEGY ENGINE
        </div>
        <div style={{ fontSize: '1.2rem', fontWeight: '700', color: '#64c8ff' }}>
          Market Making
        </div>
      </div>

      <div style={{ flex: 1 }} />

      <button
        className="btn btn-primary"
        onClick={onStart}
        disabled={isTrading}
      >
        🚀 Start Trading
      </button>

      <button
        className="btn btn-danger"
        onClick={onStop}
        disabled={!isTrading}
      >
        ⏹️ Stop Trading
      </button>

      <div style={{ 
        marginLeft: '1rem',
        padding: '0.5rem 1rem',
        background: isTrading ? 'rgba(72, 187, 120, 0.2)' : 'rgba(245, 101, 101, 0.2)',
        borderRadius: '8px',
        fontSize: '0.9rem',
        fontWeight: '600',
        color: isTrading ? '#48bb78' : '#f56565'
      }}>
        {isTrading ? '✅ ACTIVE' : '⏸️ STOPPED'}
      </div>
    </div>
  );
};

export default StrategyControls;
