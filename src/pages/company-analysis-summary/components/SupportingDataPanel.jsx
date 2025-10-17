import React from 'react';
import Icon from '../../../components/AppIcon';

const SupportingDataPanel = ({ stockData }) => {
  const formatCurrency = (value) => {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return "N/A";
    }
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })?.format(value);
  };

  const formatNumber = (value) => {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return "N/A";
    }
    if (Math.abs(value) >= 1e9) {
      return `${(value / 1e9)?.toFixed(1)}B`;
    }
    if (Math.abs(value) >= 1e6) {
      return `${(value / 1e6)?.toFixed(1)}M`;
    }
    if (Math.abs(value) >= 1e3) {
      return `${(value / 1e3)?.toFixed(1)}K`;
    }
    return value?.toString();
  };

  const getChangeColor = (change) => {
    if (change > 0) return 'text-success';
    if (change < 0) return 'text-destructive';
    return 'text-muted-foreground';
  };

  const getChangeIcon = (change) => {
    if (change > 0) return 'ArrowUp';
    if (change < 0) return 'ArrowDown';
    return 'Minus';
  };

  const dataCards = [
    {
      title: 'Current Stock Price',
      value: formatCurrency(stockData?.currentPrice),
      change: stockData?.priceChange ?? null,
      changePercent: stockData?.priceChangePercent ?? null,
      icon: 'DollarSign',
      bgColor: 'bg-primary/10',
      iconColor: 'text-primary'
    },
    {
      title: 'Trading Volume',
      value: formatNumber(stockData?.volume),
      change: stockData?.volumeChange ?? null,
      changePercent: stockData?.volumeChangePercent ?? null,
      subtitle: `Avg: ${formatNumber(stockData?.avgVolume)}`,
      icon: 'BarChart3',
      bgColor: 'bg-accent/10',
      iconColor: 'text-accent'
    },
    {
      title: 'EPS Estimate',
      value: formatCurrency(stockData?.epsEstimate),
      change: stockData?.epsChange ?? null,
      changePercent: stockData?.epsChangePercent ?? null,
      subtitle: `Prev: ${formatCurrency(stockData?.prevEps)}`,
      icon: 'TrendingUp',
      bgColor: 'bg-success/10',
      iconColor: 'text-success'
    },
    {
      title: 'Revenue Estimate',
      value: `$${formatNumber(stockData?.revenueEstimate)}`,
      change: stockData?.revenueChange ?? null,
      changePercent: stockData?.revenueChangePercent ?? null,
      subtitle: `Prev: $${formatNumber(stockData?.prevRevenue)}`,
      icon: 'PieChart',
      bgColor: 'bg-warning/10',
      iconColor: 'text-warning'
    }
  ];

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex items-center space-x-3 mb-6">
        <div className="flex items-center justify-center w-10 h-10 bg-secondary/10 rounded-lg">
          <Icon name="BarChart" size={20} className="text-secondary" strokeWidth={2} />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Supporting Data</h3>
          <p className="text-sm text-muted-foreground">Key financial metrics and comparisons</p>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {dataCards?.map((card, index) => (
          <div key={index} className="p-4 rounded-lg border border-border hover:shadow-md transition-shadow duration-200">
            <div className="flex items-center justify-between mb-3">
              <div className={`flex items-center justify-center w-8 h-8 rounded-lg ${card?.bgColor}`}>
                <Icon 
                  name={card?.icon} 
                  size={16} 
                  className={card?.iconColor}
                  strokeWidth={2}
                />
              </div>
              {card?.change !== undefined && card?.change !== null && (
                <div className={`flex items-center space-x-1 ${getChangeColor(card?.change)}`}>
                  <Icon 
                    name={getChangeIcon(card?.change)} 
                    size={12} 
                    strokeWidth={2}
                  />
                  <span className="text-xs font-medium">
                    {card?.changePercent >= 0 ? '+' : ''}{card?.changePercent}%
                  </span>
                </div>
              )}
            </div>
            
            <div className="space-y-1">
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {card?.title}
              </h4>
              <div className="text-xl font-bold text-text-primary">
                {card?.value}
              </div>
              {card?.subtitle && (
                <div className="text-xs text-muted-foreground">
                  {card?.subtitle}
                </div>
              )}
              {card?.change !== undefined && card?.change !== null && (
                <div className={`text-xs ${getChangeColor(card?.change)}`}>
                  {card?.change >= 0 ? '+' : ''}{formatCurrency(Math.abs(card?.change))} today
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-6 pt-4 border-t border-border">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-xs text-muted-foreground mb-1">Market Cap</div>
            <div className="text-sm font-semibold text-text-primary">
              ${formatNumber(stockData?.marketCap)}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground mb-1">P/E Ratio</div>
            <div className="text-sm font-semibold text-text-primary">
              {stockData?.peRatio}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground mb-1">52W High</div>
            <div className="text-sm font-semibold text-text-primary">
              {formatCurrency(stockData?.yearHigh)}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground mb-1">52W Low</div>
            <div className="text-sm font-semibold text-text-primary">
              {formatCurrency(stockData?.yearLow)}
            </div>
          </div>
        </div>
      </div>
      <div className="mt-4 pt-4 border-t border-border">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Data as of: {new Date()?.toLocaleString()}</span>
          <div className="flex items-center space-x-1">
            <Icon name="RefreshCw" size={12} strokeWidth={2} />
            <span>Real-time updates</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SupportingDataPanel;