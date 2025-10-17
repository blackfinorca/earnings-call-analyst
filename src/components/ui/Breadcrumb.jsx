import React from 'react';
import { Link } from 'react-router-dom';
import Icon from '../AppIcon';

const Breadcrumb = ({ items = [] }) => {
  if (!items || items?.length === 0) {
    return null;
  }

  return (
    <nav className="flex items-center space-x-1 text-sm text-text-secondary mb-6" aria-label="Breadcrumb">
      <ol className="flex items-center space-x-1">
        {items?.map((item, index) => {
          const isLast = index === items?.length - 1;
          
          return (
            <li key={index} className="flex items-center">
              {index > 0 && (
                <Icon 
                  name="ChevronRight" 
                  size={14} 
                  className="mx-2 text-muted-foreground" 
                  strokeWidth={2}
                />
              )}
              {isLast ? (
                <span className="font-medium text-text-primary truncate max-w-xs">
                  {item?.label}
                </span>
              ) : (
                <Link
                  to={item?.path}
                  className="hover:text-text-primary transition-colors duration-200 truncate max-w-xs"
                >
                  {item?.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};

export default Breadcrumb;