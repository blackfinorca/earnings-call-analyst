import React from 'react';
import Button from '../../../components/ui/Button';
import Icon from '../../../components/AppIcon';

const EarningsTable = ({ 
  earnings, 
  sortConfig, 
  onSort, 
  onGenerate,
  loading 
}) => {
  const getSortIcon = (column) => {
    if (sortConfig?.key !== column) {
      return <Icon name="ArrowUpDown" size={14} className="opacity-50" />;
    }
    return sortConfig?.direction === 'asc' 
      ? <Icon name="ArrowUp" size={14} />
      : <Icon name="ArrowDown" size={14} />;
  };

  const formatCurrency = (value) => {
    if (!value) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    })?.format(value);
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date?.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const getStockChangeColor = (change) => {
    if (change > 0) return 'text-success';
    if (change < 0) return 'text-destructive';
    return 'text-text-secondary';
  };

  const getStockChangeIcon = (change) => {
    if (change > 0) return 'TrendingUp';
    if (change < 0) return 'TrendingDown';
    return 'Minus';
  };

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="p-8 text-center">
          <div className="flex items-center justify-center mb-4">
            <Icon name="Loader2" size={32} className="animate-spin text-primary" />
          </div>
          <p className="text-text-secondary">Loading earnings data...</p>
        </div>
      </div>
    );
  }

  if (!earnings || earnings?.length === 0) {
    return (
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="p-8 text-center">
          <div className="flex items-center justify-center mb-4">
            <Icon name="Search" size={32} className="text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary mb-2">No earnings calls found</h3>
          <p className="text-text-secondary">Try adjusting your filters or search criteria.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
      {/* Desktop Table */}
      <div className="hidden lg:block overflow-x-auto">
        <table className="w-full">
          <thead className="bg-muted border-b border-border">
            <tr>
              <th className="text-left p-4">
                <button
                  onClick={() => onSort('ticker')}
                  className="flex items-center space-x-2 font-semibold text-text-primary hover:text-primary transition-colors"
                >
                  <span>Ticker</span>
                  {getSortIcon('ticker')}
                </button>
              </th>
              <th className="text-left p-4">
                <button
                  onClick={() => onSort('companyName')}
                  className="flex items-center space-x-2 font-semibold text-text-primary hover:text-primary transition-colors"
                >
                  <span>Company</span>
                  {getSortIcon('companyName')}
                </button>
              </th>
              <th className="text-left p-4">
                <span className="font-semibold text-text-primary">Event</span>
              </th>
              <th className="text-left p-4">
                <button
                  onClick={() => onSort('earningsDate')}
                  className="flex items-center space-x-2 font-semibold text-text-primary hover:text-primary transition-colors"
                >
                  <span>Date</span>
                  {getSortIcon('earningsDate')}
                </button>
              </th>
              <th className="text-left p-4">
                <button
                  onClick={() => onSort('stockPrice')}
                  className="flex items-center space-x-2 font-semibold text-text-primary hover:text-primary transition-colors"
                >
                  <span>Stock Price</span>
                  {getSortIcon('stockPrice')}
                </button>
              </th>
              <th className="text-left p-4">
                <span className="font-semibold text-text-primary">EPS Est.</span>
              </th>
              <th className="text-left p-4">
                <span className="font-semibold text-text-primary">Revenue Est.</span>
              </th>
              <th className="text-center p-4">
                <span className="font-semibold text-text-primary">Action</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {earnings?.map((earning, index) => (
              <tr 
                key={earning?.id} 
                className={`hover:bg-muted/50 transition-colors ${
                  index % 2 === 0 ? 'bg-background' : 'bg-muted/20'
                }`}
              >
                <td className="p-4">
                  <span className="font-mono font-semibold text-primary text-sm">
                    {earning?.ticker}
                  </span>
                </td>
                <td className="p-4">
                  <div>
                    <div className="font-medium text-text-primary">{earning?.companyName}</div>
                    <div className="text-sm text-text-secondary">{earning?.sector}</div>
                  </div>
                </td>
                <td className="p-4">
                  <span className="text-sm text-text-primary">{earning?.eventName}</span>
                </td>
                <td className="p-4">
                  <span className="text-sm text-text-primary">{formatDate(earning?.earningsDate)}</span>
                </td>
                <td className="p-4">
                  <div className="flex items-center space-x-2">
                    <span className="font-medium text-text-primary">
                      {formatCurrency(earning?.stockPrice)}
                    </span>
                    <div className={`flex items-center space-x-1 ${getStockChangeColor(earning?.priceChange)}`}>
                      <Icon name={getStockChangeIcon(earning?.priceChange)} size={12} />
                      <span className="text-xs font-medium">
                        {earning?.priceChange > 0 ? '+' : ''}{earning?.priceChange?.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                </td>
                <td className="p-4">
                  <span className="text-sm text-text-primary">{formatCurrency(earning?.epsEstimate)}</span>
                </td>
                <td className="p-4">
                  <span className="text-sm text-text-primary">
                    {earning?.revenueEstimate ? `$${(earning?.revenueEstimate / 1000000)?.toFixed(1)}M` : 'N/A'}
                  </span>
                </td>
                <td className="p-4 text-center">
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => onGenerate(earning)}
                    iconName="BarChart3"
                    iconPosition="left"
                    iconSize={14}
                  >
                  Report
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* Mobile Card Layout */}
      <div className="lg:hidden divide-y divide-border">
        {earnings?.map((earning, index) => (
          <div 
            key={earning?.id} 
            className={`p-4 ${index % 2 === 0 ? 'bg-background' : 'bg-muted/20'}`}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-2">
                  <span className="font-mono font-bold text-primary text-lg">
                    {earning?.ticker}
                  </span>
                  <div className={`flex items-center space-x-1 ${getStockChangeColor(earning?.priceChange)}`}>
                    <Icon name={getStockChangeIcon(earning?.priceChange)} size={14} />
                    <span className="text-sm font-medium">
                      {earning?.priceChange > 0 ? '+' : ''}{earning?.priceChange?.toFixed(2)}%
                    </span>
                  </div>
                </div>
                <h3 className="font-semibold text-text-primary mb-1">{earning?.companyName}</h3>
                <p className="text-sm text-text-secondary">{earning?.sector}</p>
              </div>
              <Button
                variant="default"
                size="sm"
                onClick={() => onGenerate(earning)}
                iconName="BarChart3"
                iconSize={16}
              >
                Report
              </Button>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-text-secondary">Date:</span>
                <div className="font-medium text-text-primary">{formatDate(earning?.earningsDate)}</div>
              </div>
              <div>
                <span className="text-text-secondary">Stock Price:</span>
                <div className="font-medium text-text-primary">{formatCurrency(earning?.stockPrice)}</div>
              </div>
              <div>
                <span className="text-text-secondary">EPS Est.:</span>
                <div className="font-medium text-text-primary">{formatCurrency(earning?.epsEstimate)}</div>
              </div>
              <div>
                <span className="text-text-secondary">Revenue Est.:</span>
                <div className="font-medium text-text-primary">
                  {earning?.revenueEstimate ? `$${(earning?.revenueEstimate / 1000000)?.toFixed(1)}M` : 'N/A'}
                </div>
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-border">
              <span className="text-xs text-text-secondary">{earning?.eventName}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default EarningsTable;
