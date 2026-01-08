import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import Home from "./pages/Home";
import Trading from "./pages/Trading";
import Risk from "./pages/Risk";
import Performance from "./pages/Performance";
import TradeLog from "./pages/TradeLog";

function Router() {
  return (
    <Switch>
      <Route path="/" component={Home} />
      <Route path="/trading" component={Trading} />
      <Route path="/risk" component={Risk} />
      <Route path="/performance" component={Performance} />
      <Route path="/log" component={TradeLog} />
      <Route path="/404" component={NotFound} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="dark" switchable>
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
