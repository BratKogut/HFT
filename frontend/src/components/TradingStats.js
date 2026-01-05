import React from 'react';

const TradingStats = ({ positions, isTrading }) => {
  // Calculate total PnL
  const totalUnrealizedPnL = positions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0);
  const totalRealizedPnL = positions.reduce((sum, pos) => sum + (pos.realized_pnl || 0), 0);
  const totalPnL = totalUnrealizedPnL + totalRealizedPnL;

  // Calculate total exposure
  const totalExposure = positions.reduce((sum, pos) => {
    return sum + Math.abs(pos.size * pos.current_price);
  }, 0);

  const stats = [
    {
      label: 'Total PnL',
      value: `$${totalPnL.toFixed(2)}`,
      positive: totalPnL >= 0
    },
    {
      label: 'Unrealized PnL',
      value: `$${totalUnrealizedPnL.toFixed(2)}`,
      positive: totalUnrealizedPnL >= 0
    },
    {
      label: 'Realized PnL',
      value: `$${totalRealizedPnL.toFixed(2)}`,
      positive: totalRealizedPnL >= 0
    },
    {
      label: 'Total Exposure',
      value: `$${totalExposure.toFixed(2)}`,
      positive: null
    },
    {
      label: 'Open Positions',
      value: positions.length.toString(),
      positive: null
    },
    {
      label: 'Trading Status',
      value: isTrading ? 'ACTIVE' : 'STOPPED',
      positive: isTrading
    }
  ];

  return (
    <div>
      <h2>📊 Trading Statistics</h2>
      
      {/* Stats Grid */}
      <div className="stats-grid">
        {stats.map((stat, index) => (
          <div key={index} className="stat-card">
            <div className="stat-label">{stat.label}</div>
            <div className={`stat-value ${
              stat.positive === true ? 'positive' : 
              stat.positive === false ? 'negative' : ''
            }`}>
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Positions Table */}
      {positions.length > 0 && (
        <div style={{ marginTop: '1.5rem' }}>
          <h3 style={{ fontSize: '0.9rem', color: '#a0aec0', marginBottom: '0.75rem' }}>
            Open Positions
          </h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ 
                  borderBottom: '1px solid rgba(100, 200, 255, 0.2)',
                  color: '#a0aec0'
                }}>
                  <th style={{ padding: '0.5rem', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>Size</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>Entry</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>Current</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>Unrealized PnL</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>Realized PnL</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((position, index) => (
                  <tr key={index} style={{ 
                    borderBottom: '1px solid rgba(100, 200, 255, 0.1)' 
                  }}>
                    <td style={{ padding: '0.5rem', fontWeight: '600' }}>
                      {position.symbol}
                    </td>
                    <td style={{ 
                      padding: '0.5rem', 
                      textAlign: 'right',
                      color: position.size > 0 ? '#48bb78' : '#f56565'
                    }}>
                      {position.size > 0 ? '+' : ''}{position.size.toFixed(4)}
                    </td>
                    <td style={{ padding: '0.5rem', textAlign: 'right' }}>
                      ${position.entry_price.toFixed(2)}
                    </td>
                    <td style={{ padding: '0.5rem', textAlign: 'right' }}>
                      ${position.current_price.toFixed(2)}
                    </td>
                    <td style={{ 
                      padding: '0.5rem', 
                      textAlign: 'right',
                      color: position.unrealized_pnl >= 0 ? '#48bb78' : '#f56565',
                      fontWeight: '600'
                    }}>
                      ${position.unrealized_pnl.toFixed(2)}
                    </td>
                    <td style={{ 
                      padding: '0.5rem', 
                      textAlign: 'right',
                      color: position.realized_pnl >= 0 ? '#48bb78' : '#f56565'
                    }}>
                      ${position.realized_pnl.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {positions.length === 0 && (
        <div className="no-data" style={{ marginTop: '1rem' }}>
          No open positions
        </div>
      )}
    </div>
  );
};

export default TradingStats;
