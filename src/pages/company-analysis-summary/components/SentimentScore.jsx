import React from 'react';
import Icon from '../../../components/AppIcon';

const SentimentScore = ({ sentiment, score, confidence }) => {
  const getSentimentColor = (sentiment) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
        return 'text-success';
      case 'negative':
        return 'text-destructive';
      case 'neutral':
        return 'text-warning';
      default:
        return 'text-muted-foreground';
    }
  };

  const getSentimentBgColor = (sentiment) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
        return 'bg-success/10 border-success/20';
      case 'negative':
        return 'bg-destructive/10 border-destructive/20';
      case 'neutral':
        return 'bg-warning/10 border-warning/20';
      default:
        return 'bg-muted/10 border-border';
    }
  };

  const getSentimentIcon = (sentiment) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
        return 'TrendingUp';
      case 'negative':
        return 'TrendingDown';
      case 'neutral':
        return 'Minus';
      default:
        return 'HelpCircle';
    }
  };

  return (
    <div className={`bg-card border rounded-xl p-8 text-center ${getSentimentBgColor(sentiment)}`}>
      <div className="flex flex-col items-center space-y-4">
        <div className={`flex items-center justify-center w-16 h-16 rounded-full ${getSentimentBgColor(sentiment)} ${getSentimentColor(sentiment)}`}>
          <Icon 
            name={getSentimentIcon(sentiment)} 
            size={32} 
            strokeWidth={2.5}
          />
        </div>
        
        <div className="space-y-2">
          <h2 className="text-3xl font-bold text-text-primary">
            Pre-Call Sentiment
          </h2>
          
          <div className={`text-6xl font-bold ${getSentimentColor(sentiment)}`}>
            {score}/100
          </div>
          
          <div className="flex items-center justify-center space-x-2">
            <span className={`text-xl font-semibold capitalize ${getSentimentColor(sentiment)}`}>
              {sentiment}
            </span>
            <div className="w-2 h-2 rounded-full bg-border"></div>
            <span className="text-sm text-muted-foreground">
              {confidence}% Confidence
            </span>
          </div>
        </div>
        
        <div className="w-full max-w-md">
          <div className="flex justify-between text-xs text-muted-foreground mb-2">
            <span>Bearish</span>
            <span>Neutral</span>
            <span>Bullish</span>
          </div>
          <div className="w-full bg-muted rounded-full h-2">
            <div 
              className={`h-2 rounded-full transition-all duration-500 ${
                sentiment?.toLowerCase() === 'positive' ? 'bg-success' :
                sentiment?.toLowerCase() === 'negative'? 'bg-destructive' : 'bg-warning'
              }`}
              style={{ width: `${score}%` }}
            ></div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SentimentScore;