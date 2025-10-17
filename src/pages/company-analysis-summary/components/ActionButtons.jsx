import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../../components/ui/Button';

const ActionButtons = ({ onAnalyzeAnother }) => {
  const navigate = useNavigate();

  const handleBackToDashboard = () => {
    navigate('/earnings-dashboard');
  };

  const handleAnalyzeAnother = () => {
    if (onAnalyzeAnother) {
      onAnalyzeAnother();
    } else {
      navigate('/earnings-dashboard');
    }
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex flex-col sm:flex-row gap-4">
        <Button
          variant="outline"
          size="lg"
          iconName="ArrowLeft"
          iconPosition="left"
          onClick={handleBackToDashboard}
          className="flex-1 sm:flex-none"
        >
          Back to Dashboard
        </Button>
        
        <Button
          variant="default"
          size="lg"
          iconName="Search"
          iconPosition="left"
          onClick={handleAnalyzeAnother}
          className="flex-1"
        >
          Analyze Another Company
        </Button>
      </div>
      
      <div className="mt-4 pt-4 border-t border-border">
        <div className="flex flex-col sm:flex-row gap-3">
          <Button
            variant="ghost"
            size="sm"
            iconName="Download"
            iconPosition="left"
            className="flex-1 sm:flex-none"
          >
            Export Report
          </Button>
          
          <Button
            variant="ghost"
            size="sm"
            iconName="Share"
            iconPosition="left"
            className="flex-1 sm:flex-none"
          >
            Share Analysis
          </Button>
          
          <Button
            variant="ghost"
            size="sm"
            iconName="Bookmark"
            iconPosition="left"
            className="flex-1 sm:flex-none"
          >
            Save to Watchlist
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ActionButtons;