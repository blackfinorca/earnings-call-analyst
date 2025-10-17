import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import Icon from '../AppIcon';

const Header = () => {
  const location = useLocation();

  const navigationItems = [
    {
      label: 'Earnings Dashboard',
      path: '/earnings-dashboard',
      icon: 'BarChart3'
    },
    {
      label: 'Company Analysis',
      path: '/company-analysis-summary',
      icon: 'Building2'
    }
  ];

  const isActivePath = (path) => {
    return location?.pathname === path;
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-surface border-b border-border shadow-md">
      <div className="flex items-center justify-between h-16 px-6">
        {/* Logo/Brand Section */}
        <div className="flex items-center">
          <Link 
            to="/earnings-dashboard" 
            className="flex items-center space-x-3 hover:opacity-80 transition-all duration-300"
          >
            <div className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-primary via-primary to-accent rounded-xl shadow-lg">
              <Icon 
                name="TrendingUp" 
                size={22} 
                color="var(--color-primary-foreground)" 
                strokeWidth={2.5}
              />
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-bold text-text-primary leading-tight tracking-tight">
                Earnings call Analyst
              </span>
              <span className="text-xs text-text-secondary leading-tight font-medium">
                AI-Powered Investment Intelligence
              </span>
            </div>
          </Link>
        </div>

        {/* Navigation Items */}
        <nav className="hidden md:flex items-center space-x-2">
          {navigationItems?.map((item) => (
            <Link
              key={item?.path}
              to={item?.path}
              className={`
                flex items-center space-x-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 transform hover:scale-105
                ${isActivePath(item?.path)
                  ? 'bg-gradient-to-r from-primary to-accent text-primary-foreground shadow-lg shadow-primary/25'
                  : 'text-text-secondary hover:text-text-primary hover:bg-gradient-to-r hover:from-muted hover:to-gray-100'
                }
              `}
            >
              <Icon 
                name={item?.icon} 
                size={16} 
                strokeWidth={2.5}
              />
              <span>{item?.label}</span>
            </Link>
          ))}
        </nav>

        {/* Mobile Menu Button */}
        <div className="md:hidden">
          <button
            className="flex items-center justify-center w-10 h-10 rounded-xl text-text-secondary hover:text-text-primary hover:bg-muted transition-all duration-300"
            aria-label="Open navigation menu"
          >
            <Icon name="Menu" size={20} strokeWidth={2} />
          </button>
        </div>

        {/* User Actions */}
        <div className="hidden md:flex items-center space-x-3">
          <button
            className="flex items-center justify-center w-10 h-10 rounded-xl text-text-secondary hover:text-primary hover:bg-muted transition-all duration-300 transform hover:scale-105"
            aria-label="Notifications"
          >
            <Icon name="Bell" size={18} strokeWidth={2} />
          </button>
          
          <button
            className="flex items-center justify-center w-10 h-10 rounded-xl text-text-secondary hover:text-primary hover:bg-muted transition-all duration-300 transform hover:scale-105"
            aria-label="Settings"
          >
            <Icon name="Settings" size={18} strokeWidth={2} />
          </button>

          <div className="w-px h-6 bg-border mx-2"></div>

          <button
            className="flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-primary to-accent text-primary-foreground text-sm font-bold hover:shadow-lg hover:shadow-primary/25 transition-all duration-300 transform hover:scale-105"
            aria-label="User profile"
          >
            <Icon name="User" size={16} strokeWidth={2.5} />
          </button>
        </div>
      </div>
      {/* Mobile Navigation Overlay - Hidden by default */}
      <div className="hidden md:hidden absolute top-full left-0 right-0 bg-surface border-b border-border shadow-lg">
        <nav className="px-6 py-4 space-y-2">
          {navigationItems?.map((item) => (
            <Link
              key={item?.path}
              to={item?.path}
              className={`
                flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200
                ${isActivePath(item?.path)
                  ? 'bg-gradient-to-r from-primary to-accent text-primary-foreground'
                  : 'text-text-secondary hover:text-text-primary hover:bg-muted'
                }
              `}
            >
              <Icon 
                name={item?.icon} 
                size={18} 
                strokeWidth={2}
              />
              <span>{item?.label}</span>
            </Link>
          ))}
          
          <div className="border-t border-border pt-4 mt-4">
            <div className="flex items-center space-x-4">
              <button
                className="flex items-center space-x-2 px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors duration-200"
                aria-label="Notifications"
              >
                <Icon name="Bell" size={18} strokeWidth={2} />
                <span>Notifications</span>
              </button>
              
              <button
                className="flex items-center space-x-2 px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors duration-200"
                aria-label="Settings"
              >
                <Icon name="Settings" size={18} strokeWidth={2} />
                <span>Settings</span>
              </button>
            </div>
          </div>
        </nav>
      </div>
    </header>
  );
};

export default Header;