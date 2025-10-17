import React from 'react';
import Icon from '../../../components/AppIcon';

const DataCollectionStatus = ({ statusData }) => {
  const getStatusIcon = (label) => {
    if (label?.includes('Earnings')) return 'TrendingUp';
    if (label?.includes('News')) return 'Newspaper';
    if (label?.includes('Stock')) return 'BarChart3';
    if (label?.includes('AI')) return 'Brain';
    return 'Activity';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'text-success bg-success/10 border-success/20';
      case 'in-progress':
        return 'text-primary bg-primary/10 border-primary/20';
      case 'pending':
        return 'text-warning bg-warning/10 border-warning/20';
      case 'error':
        return 'text-destructive bg-destructive/10 border-destructive/20';
      default:
        return 'text-muted-foreground bg-muted/10 border-border';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'completed':
        return 'Complete';
      case 'in-progress':
        return 'Processing';
      case 'pending':
        return 'Pending';
      case 'error':
        return 'Error';
      default:
        return 'Unknown';
    }
  };

  const getStatusIndicator = (status) => {
    switch (status) {
      case 'completed':
        return 'CheckCircle';
      case 'in-progress':
        return 'Loader2';
      case 'pending':
        return 'Clock';
      case 'error':
        return 'XCircle';
      default:
        return 'Circle';
    }
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex items-center space-x-3 mb-6">
        <div className="flex items-center justify-center w-10 h-10 bg-primary/10 rounded-lg">
          <Icon name="Activity" size={20} className="text-primary" strokeWidth={2} />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Data Collection Status</h3>
          <p className="text-sm text-muted-foreground">Real-time processing updates</p>
        </div>
      </div>
      
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statusData?.map((item, index) => (
          <div key={index} className={`relative border rounded-xl p-4 transition-all duration-300 hover:shadow-sm ${getStatusColor(item?.status)}`}>
            {/* Status Icon */}
            <div className="flex items-center justify-center w-12 h-12 mx-auto mb-3">
              <Icon 
                name={getStatusIcon(item?.label)} 
                size={24} 
                strokeWidth={2}
                className={`${item?.status === 'completed' ? 'text-success' : 
                           item?.status === 'in-progress' ? 'text-primary' :
                           item?.status === 'pending' ? 'text-warning' : 
                           item?.status === 'error' ? 'text-destructive' : 'text-muted-foreground'}`}
              />
            </div>

            {/* Label */}
            <div className="text-center">
              <h4 className="text-sm font-medium text-text-primary mb-1">
                {item?.label}
              </h4>
              
              {/* Status Badge */}
              <div className="flex items-center justify-center space-x-1 mb-2">
                <Icon 
                  name={getStatusIndicator(item?.status)} 
                  size={12} 
                  className={`${
                    item?.status === 'completed' ? 'text-success' :
                    item?.status === 'in-progress' ? 'text-primary animate-spin' :
                    item?.status === 'pending' ? 'text-warning' :
                    item?.status === 'error' ? 'text-destructive' : 'text-muted-foreground'
                  }`}
                />
                <span className={`text-xs font-medium ${
                  item?.status === 'completed' ? 'text-success' :
                  item?.status === 'in-progress' ? 'text-primary' :
                  item?.status === 'pending' ? 'text-warning' :
                  item?.status === 'error' ? 'text-destructive' : 'text-muted-foreground'
                }`}>
                  {getStatusText(item?.status)}
                </span>
              </div>

              {/* Progress Bar for in-progress items */}
              {item?.status === 'in-progress' && (
                <div className="w-full bg-muted rounded-full h-1.5 mb-2">
                  <div 
                    className="h-1.5 rounded-full bg-primary transition-all duration-500"
                    style={{ width: `${item?.progress}%` }}
                  ></div>
                </div>
              )}

              {/* Count Badge */}
              {item?.count && (
                <div className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-muted text-muted-foreground">
                  {item?.count}
                </div>
              )}
            </div>

            {/* Completion Checkmark */}
            {item?.status === 'completed' && (
              <div className="absolute -top-2 -right-2 w-6 h-6 bg-success rounded-full flex items-center justify-center">
                <Icon name="Check" size={12} className="text-white" strokeWidth={3} />
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-6 pt-4 border-t border-border">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Last updated: {new Date()?.toLocaleTimeString()}</span>
          <div className="flex items-center space-x-1">
            <div className="w-2 h-2 bg-success rounded-full animate-pulse"></div>
            <span>Live updates</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataCollectionStatus;