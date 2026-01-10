import React from 'react';

const OrderBook = ({ data }) => {
  if (!data || data.error) {
    return (
      <div>
        <h2>📊 Order Book</h2>
        <div className="no-data">No order book data available</div>
      </div>
    );
  }

  const { bids = [], asks = [], mid_price, spread, spread_bps, imbalance } = data;

  // Calculate max volume for visualization
  const maxVolume = Math.max(
    ...bids.slice(0, 10).map(level => level[1]),
    ...asks.slice(0, 10).map(level => level[1])
  );

  return (
    <div>
      <h2>📊 Order Book</h2>
      
      {/* Order Book Info */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-around', 
        marginBottom: '1rem',
        padding: '0.75rem',
        background: 'rgba(100, 200, 255, 0.05)',
        borderRadius: '8px'
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: '#a0aec0' }}>MID PRICE</div>
          <div style={{ fontSize: '1.2rem', fontWeight: '700', color: '#64c8ff' }}>
            ${mid_price?.toFixed(2) || '0.00'}
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: '#a0aec0' }}>SPREAD</div>
          <div style={{ fontSize: '1.2rem', fontWeight: '700', color: '#ffc864' }}>
            {spread_bps?.toFixed(2) || '0.00'} bps
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: '#a0aec0' }}>IMBALANCE</div>
          <div style={{ 
            fontSize: '1.2rem', 
            fontWeight: '700',
            color: imbalance > 0 ? '#48bb78' : (imbalance < 0 ? '#f56565' : '#a0aec0')
          }}>
            {(imbalance * 100)?.toFixed(1) || '0.0'}%
          </div>
        </div>
      </div>

      {/* Order Book Levels */}
      <div className="orderbook-container">
        {/* Bids */}
        <div className="orderbook-side">
          <h3>🟢 Bids</h3>
          {bids.slice(0, 10).map((level, index) => {
            const [price, size] = level;
            const volumeWidth = (size / maxVolume) * 100;
            return (
              <div 
                key={`bid-${index}`} 
                className="orderbook-level bid-level"
                style={{ '--volume-width': `${volumeWidth}%` }}
              >
                <span className="price">{price.toFixed(2)}</span>
                <span className="size">{size.toFixed(4)}</span>
              </div>
            );
          })}
        </div>

        {/* Asks */}
        <div className="orderbook-side">
          <h3>🔴 Asks</h3>
          {asks.slice(0, 10).map((level, index) => {
            const [price, size] = level;
            const volumeWidth = (size / maxVolume) * 100;
            return (
              <div 
                key={`ask-${index}`} 
                className="orderbook-level ask-level"
                style={{ '--volume-width': `${volumeWidth}%` }}
              >
                <span className="price">{price.toFixed(2)}</span>
                <span className="size">{size.toFixed(4)}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default OrderBook;
