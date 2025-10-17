import React from 'react';
import Icon from '../../../components/AppIcon';

const InvestmentRecommendation = ({ recommendation }) => {
  const getRecommendationColor = (type) => {
    switch (type?.toLowerCase()) {
      case 'buy': case'strong buy':
        return 'text-success';
      case 'sell': case'strong sell':
        return 'text-destructive';
      case 'hold':
        return 'text-warning';
      default:
        return 'text-muted-foreground';
    }
  };

  const getRecommendationBg = (type) => {
    switch (type?.toLowerCase()) {
      case 'buy': case'strong buy':
        return 'bg-success/10 border-success/20';
      case 'sell': case'strong sell':
        return 'bg-destructive/10 border-destructive/20';
      case 'hold':
        return 'bg-warning/10 border-warning/20';
      default:
        return 'bg-muted/10 border-border';
    }
  };

  const getRecommendationIcon = (type) => {
    switch (type?.toLowerCase()) {
      case 'buy': case'strong buy':
        return 'ArrowUp';
      case 'sell': case'strong sell':
        return 'ArrowDown';
      case 'hold':
        return 'Minus';
      default:
        return 'HelpCircle';
    }
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex items-center space-x-3 mb-6">
        <div className="flex items-center justify-center w-10 h-10 bg-primary/10 rounded-lg">
          <Icon name="Target" size={20} className="text-primary" strokeWidth={2} />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Investment Recommendation</h3>
          <p className="text-sm text-muted-foreground">AI-powered analysis and actionable insights</p>
        </div>
      </div>
      <div className={`rounded-xl p-6 border-2 ${getRecommendationBg(recommendation?.type)} mb-6`}>
        <div className="flex items-center justify-center space-x-3 mb-4">
          <div className={`flex items-center justify-center w-12 h-12 rounded-full ${getRecommendationBg(recommendation?.type)} ${getRecommendationColor(recommendation?.type)}`}>
            <Icon 
              name={getRecommendationIcon(recommendation?.type)} 
              size={24} 
              strokeWidth={2.5}
            />
          </div>
          <div className="text-center">
            <div className={`text-2xl font-bold ${getRecommendationColor(recommendation?.type)}`}>
              {recommendation?.type}
            </div>
            <div className="text-sm text-muted-foreground">
              Confidence: {recommendation?.confidence}%
            </div>
          </div>
        </div>

        {recommendation?.targetPrice && (
          <div className="text-center mb-4">
            <div className="text-sm text-muted-foreground">Target Price</div>
            <div className="text-xl font-semibold text-text-primary">
              ${recommendation?.targetPrice}
            </div>
            <div className={`text-sm ${recommendation?.upside >= 0 ? 'text-success' : 'text-destructive'}`}>
              {recommendation?.upside >= 0 ? '+' : ''}{recommendation?.upside}% upside potential
            </div>
          </div>
        )}
      </div>
      <div className="space-y-4">
        <div>
          <h4 className="font-medium text-text-primary mb-2 flex items-center space-x-2">
            <Icon name="FileText" size={16} strokeWidth={2} />
            <span>Rationale</span>
          </h4>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {recommendation?.rationale}
          </p>
        </div>

        {recommendation?.keyFactors && recommendation?.keyFactors?.length > 0 && (
          <div>
            <h4 className="font-medium text-text-primary mb-3 flex items-center space-x-2">
              <Icon name="CheckSquare" size={16} strokeWidth={2} />
              <span>Key Supporting Factors</span>
            </h4>
            <div className="space-y-2">
              {recommendation?.keyFactors?.map((factor, index) => (
                <div key={index} className="flex items-start space-x-3 p-3 rounded-lg bg-muted/30">
                  <div className="flex items-center justify-center w-5 h-5 bg-success/20 rounded-full mt-0.5">
                    <Icon name="Check" size={12} className="text-success" strokeWidth={2} />
                  </div>
                  <span className="text-sm text-text-primary">{factor}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {recommendation?.risks && recommendation?.risks?.length > 0 && (
          <div>
            <h4 className="font-medium text-text-primary mb-3 flex items-center space-x-2">
              <Icon name="AlertTriangle" size={16} strokeWidth={2} />
              <span>Risk Considerations</span>
            </h4>
            <div className="space-y-2">
              {recommendation?.risks?.map((risk, index) => (
                <div key={index} className="flex items-start space-x-3 p-3 rounded-lg bg-warning/10">
                  <div className="flex items-center justify-center w-5 h-5 bg-warning/20 rounded-full mt-0.5">
                    <Icon name="AlertCircle" size={12} className="text-warning" strokeWidth={2} />
                  </div>
                  <span className="text-sm text-text-primary">{risk}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      <div className="mt-6 pt-4 border-t border-border">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Analysis generated: {new Date()?.toLocaleDateString()}</span>
          <div className="flex items-center space-x-1">
            <Icon name="Shield" size={12} strokeWidth={2} />
            <span>Risk-adjusted recommendation</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InvestmentRecommendation;