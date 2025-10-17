import React from 'react';
import Icon from '../AppIcon';

const LoadingSpinner = ({ 
  size = 'default', 
  text = '', 
  className = '',
  variant = 'default'
}) => {
  const sizeClasses = {
    sm: 'w-4 h-4',
    default: 'w-6 h-6',
    lg: 'w-8 h-8',
    xl: 'w-12 h-12'
  };

  const textSizeClasses = {
    sm: 'text-xs',
    default: 'text-sm',
    lg: 'text-base',
    xl: 'text-lg'
  };

  const variantClasses = {
    default: 'text-primary',
    muted: 'text-muted-foreground',
    white: 'text-white'
  };

  return (
    <div className={`flex flex-col items-center justify-center space-y-2 ${className}`}>
      <div className={`${sizeClasses?.[size]} ${variantClasses?.[variant]} animate-spin`}>
        <Icon name="Loader2" size={size === 'sm' ? 16 : size === 'lg' ? 32 : size === 'xl' ? 48 : 24} strokeWidth={2} />
      </div>
      {text && (
        <p className={`${textSizeClasses?.[size]} ${variantClasses?.[variant]} font-medium animate-pulse`}>
          {text}
        </p>
      )}
    </div>
  );
};

const LoadingSkeleton = ({ 
  lines = 3, 
  className = '',
  showAvatar = false 
}) => {
  return (
    <div className={`animate-pulse ${className}`}>
      {showAvatar && (
        <div className="flex items-center space-x-3 mb-4">
          <div className="w-10 h-10 bg-muted rounded-full shimmer"></div>
          <div className="flex-1">
            <div className="h-4 bg-muted rounded shimmer mb-2" style={{ width: '60%' }}></div>
            <div className="h-3 bg-muted rounded shimmer" style={{ width: '40%' }}></div>
          </div>
        </div>
      )}
      <div className="space-y-3">
        {Array.from({ length: lines })?.map((_, index) => (
          <div
            key={index}
            className="h-4 bg-muted rounded shimmer"
            style={{
              width: index === lines - 1 ? '75%' : '100%'
            }}
          ></div>
        ))}
      </div>
    </div>
  );
};

const LoadingCard = ({ className = '' }) => {
  return (
    <div className={`bg-card border border-border rounded-lg p-6 ${className}`}>
      <LoadingSkeleton lines={4} showAvatar />
    </div>
  );
};

const LoadingTable = ({ 
  rows = 5, 
  columns = 4, 
  className = '' 
}) => {
  return (
    <div className={`bg-card border border-border rounded-lg overflow-hidden ${className}`}>
      {/* Table Header */}
      <div className="border-b border-border p-4">
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
          {Array.from({ length: columns })?.map((_, index) => (
            <div key={index} className="h-4 bg-muted rounded shimmer"></div>
          ))}
        </div>
      </div>
      {/* Table Rows */}
      <div className="divide-y divide-border">
        {Array.from({ length: rows })?.map((_, rowIndex) => (
          <div key={rowIndex} className="p-4">
            <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
              {Array.from({ length: columns })?.map((_, colIndex) => (
                <div 
                  key={colIndex} 
                  className="h-4 bg-muted rounded shimmer"
                  style={{
                    width: colIndex === 0 ? '80%' : colIndex === columns - 1 ? '60%' : '100%'
                  }}
                ></div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default LoadingSpinner;
export { LoadingSkeleton, LoadingCard, LoadingTable };