import { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import OrderBook from './components/OrderBook';
import TradingStats from './components/TradingStats';
import LatencyMonitor from './components/LatencyMonitor';
import StrategyControls from './components/StrategyControls';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8001/ws';

function App() {
  const [systemStatus, setSystemStatus] = useState(null);
  const [orderBook, setOrderBook] = useState(null);
  const [isTrading, setIsTrading] = useState(false);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [ws, setWs] = useState(null);

  // Fetch system status
  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/status`);
      setSystemStatus(response.data);
      setIsTrading(response.data.is_trading);
    } catch (error) {
      console.error('Error fetching status:', error);
    }
  };

  // Fetch order book
  const fetchOrderBook = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/orderbook`);
      setOrderBook(response.data);
    } catch (error) {
      console.error('Error fetching order book:', error);
    }
  };

  // WebSocket connection
  useEffect(() => {
    let websocket;
    let reconnectTimeout;

    const connect = () => {
      try {
        websocket = new WebSocket(WS_URL);
        
        websocket.onopen = () => {
          console.log('WebSocket connected');
          setWsStatus('connected');
          setWs(websocket);
        };

        websocket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            
            // Handle different message types
            if (data.latency) {
              setSystemStatus(prevStatus => ({
                ...prevStatus,
                latency: data.latency
              }));
            }
            
            if (data.type === 'trading_status') {
              setIsTrading(data.status === 'started');
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        websocket.onerror = (error) => {
          console.error('WebSocket error:', error);
          setWsStatus('error');
        };

        websocket.onclose = () => {
          console.log('WebSocket disconnected');
          setWsStatus('disconnected');
          
          // Attempt to reconnect after 3 seconds
          reconnectTimeout = setTimeout(() => {
            console.log('Attempting to reconnect...');
            connect();
          }, 3000);
        };
      } catch (error) {
        console.error('WebSocket connection error:', error);
      }
    };

    connect();

    // Cleanup
    return () => {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (websocket) {
        websocket.close();
      }
    };
  }, []);

  // Poll status and order book
  useEffect(() => {
    fetchStatus();
    fetchOrderBook();
    
    const statusInterval = setInterval(fetchStatus, 1000);
    const orderBookInterval = setInterval(fetchOrderBook, 500);
    
    return () => {
      clearInterval(statusInterval);
      clearInterval(orderBookInterval);
    };
  }, []);

  // Start/Stop trading
  const handleStartTrading = async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/trading/start`);
      setIsTrading(true);
    } catch (error) {
      console.error('Error starting trading:', error);
    }
  };

  const handleStopTrading = async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/trading/stop`);
      setIsTrading(false);
    } catch (error) {
      console.error('Error stopping trading:', error);
    }
  };

  return (
    <div className="App">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <h1>⚡ HFT System <span className="tier-badge">Tier 1 MVP</span></h1>
          <div className="status-indicator">
            <span className={`status-dot ${wsStatus === 'connected' ? 'online' : 'offline'}`}></span>
            <span>{wsStatus === 'connected' ? 'Online' : 'Offline'}</span>
          </div>
        </div>
        <div className="header-right">
          <div className="symbol-display">
            {systemStatus?.symbol || 'BTC/USD'}
          </div>
          <div className="mode-badge">
            {systemStatus?.exchange_mode || 'simulator'}
          </div>
        </div>
      </header>

      {/* Main Dashboard */}
      <div className="dashboard">
        {/* Controls */}
        <div className="controls-section">
          <StrategyControls 
            isTrading={isTrading}
            onStart={handleStartTrading}
            onStop={handleStopTrading}
          />
        </div>

        {/* Top Row */}
        <div className="dashboard-row">
          {/* Order Book */}
          <div className="panel panel-large">
            <OrderBook data={orderBook} />
          </div>

          {/* Latency Monitor */}
          <div className="panel panel-medium">
            <LatencyMonitor latency={systemStatus?.latency || {}} />
          </div>
        </div>

        {/* Bottom Row */}
        <div className="dashboard-row">
          {/* Trading Stats */}
          <div className="panel panel-full">
            <TradingStats 
              positions={systemStatus?.positions || []}
              isTrading={isTrading}
            />
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="footer">
        <span>© 2026 HFT System - Educational Purpose Only</span>
        <span>Latency: {systemStatus?.latency?.total?.mean_ms?.toFixed(2) || '0.00'} ms</span>
      </footer>
    </div>
  );
}

export default App;
