import React from 'react';

const LatencyMonitor = ({ latency }) => {
  const formatLatency = (microseconds) => {
    if (!microseconds) return '0.00';
    return (microseconds / 1000).toFixed(2); // Convert to milliseconds
  };

  const getLatencyColor = (ms) => {
    if (ms < 5) return '#48bb78'; // Green
    if (ms < 20) return '#ffc864'; // Yellow
    return '#f56565'; // Red
  };

  const latencyStages = [
    { name: 'Market Data', key: 'market_data', target: '1-5 ms' },
    { name: 'Strategy', key: 'strategy', target: '1-10 ms' },
    { name: 'Risk Checks', key: 'risk', target: '<1 ms' },
    { name: 'Execution', key: 'execution', target: '10-30 ms' },
    { name: 'Total E2E', key: 'total', target: '11-40 ms' }
  ];

  return (
    <div>
      <h2>⏱️ Latency Monitor</h2>
      <div className="latency-grid">
        {latencyStages.map(stage => {
          const stageData = latency[stage.key] || {};
          const meanMs = formatLatency(stageData.mean_us);
          const p99Ms = formatLatency(stageData.p99_us);
          const color = getLatencyColor(parseFloat(meanMs));

          return (
            <div key={stage.key} className="latency-item">
              <div className="latency-label">{stage.name}</div>
              <div className="latency-value" style={{ color }}>
                {meanMs}
                <span className="latency-unit">ms</span>
              </div>
              <div style={{ 
                fontSize: '0.7rem', 
                color: '#a0aec0',
                marginTop: '0.3rem' 
              }}>
                P99: {p99Ms}ms | Target: {stage.target}
              </div>
            </div>
          );
        })}
      </div>

      {/* Latency Breakdown Chart */}
      {Object.keys(latency).length > 0 && (
        <div style={{ marginTop: '1.5rem' }}>
          <h3 style={{ fontSize: '0.9rem', color: '#a0aec0', marginBottom: '0.5rem' }}>
            Latency Breakdown
          </h3>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end', height: '100px' }}>
            {latencyStages.slice(0, 4).map(stage => {
              const stageData = latency[stage.key] || {};
              const meanMs = parseFloat(formatLatency(stageData.mean_us));
              const maxHeight = 40; // max 40ms on scale
              const height = Math.min((meanMs / maxHeight) * 100, 100);
              const color = getLatencyColor(meanMs);

              return (
                <div key={`bar-${stage.key}`} style={{ flex: 1, textAlign: 'center' }}>
                  <div style={{
                    height: `${height}%`,
                    background: color,
                    borderRadius: '4px 4px 0 0',
                    transition: 'all 0.3s ease',
                    minHeight: '5px'
                  }} />
                  <div style={{ fontSize: '0.6rem', color: '#a0aec0', marginTop: '0.3rem' }}>
                    {stage.name.split(' ')[0]}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: color, fontWeight: '600' }}>
                    {meanMs}ms
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default LatencyMonitor;
