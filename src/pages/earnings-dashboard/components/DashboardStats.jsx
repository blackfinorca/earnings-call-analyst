import React from 'react';
import Icon from '../../../components/AppIcon';

const DashboardStats = ({ stats, loading }) => {
  const statItems = [
    {
      id: 'total',
      label: 'Total Companies',
      value: stats?.total || 0,
      icon: 'Building2',
      color: 'text-primary',
      bgColor: 'bg-primary/10'
    },
    {
      id: 'thisWeek',
      label: 'This Week',
      value: stats?.thisWeek || 0,
      icon: 'Calendar',
      color: 'text-success',
      bgColor: 'bg-success/10'
    },
    {
      id: 'nextWeek',
      label: 'Next Week',
      value: stats?.nextWeek || 0,
      icon: 'CalendarDays',
      color: 'text-warning',
      bgColor: 'bg-warning/10'
    },
    {
      id: 'sectors',
      label: 'Sectors',
      value: stats?.sectors || 0,
      icon: 'PieChart',
      color: 'text-accent',
      bgColor: 'bg-accent/10'
    }
  ];

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {Array.from({ length: 4 })?.map((_, index) => (
          <div key={index} className="bg-card border border-border rounded-lg p-6">
            <div className="animate-pulse">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 bg-muted rounded-lg shimmer"></div>
                <div className="w-8 h-4 bg-muted rounded shimmer"></div>
              </div>
              <div className="w-16 h-8 bg-muted rounded shimmer mb-2"></div>
              <div className="w-24 h-4 bg-muted rounded shimmer"></div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {statItems?.map((item) => (
        <div 
          key={item?.id} 
          className="bg-card border border-border rounded-lg p-6 hover:shadow-md transition-shadow duration-200"
        >
          <div className="flex items-center justify-between mb-4">
            <div className={`flex items-center justify-center w-10 h-10 rounded-lg ${item?.bgColor}`}>
              <Icon 
                name={item?.icon} 
                size={20} 
                className={item?.color}
                strokeWidth={2}
              />
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-text-primary">
                {item?.value?.toLocaleString()}
              </div>
            </div>
          </div>
          
          <div>
            <h3 className="text-sm font-medium text-text-secondary mb-1">
              {item?.label}
            </h3>
            <div className="flex items-center space-x-2">
              <div className="flex-1 bg-muted rounded-full h-1.5">
                <div 
                  className={`h-1.5 rounded-full transition-all duration-500 ${
                    item?.id === 'total' ? 'bg-primary' :
                    item?.id === 'thisWeek' ? 'bg-success' :
                    item?.id === 'nextWeek' ? 'bg-warning' : 'bg-accent'
                  }`}
                  style={{ 
                    width: item?.id === 'total' ? '100%' : 
                           item?.id === 'sectors' ? '85%' :
                           `${Math.min((item?.value / (stats?.total || 1)) * 100, 100)}%` 
                  }}
                ></div>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default DashboardStats;