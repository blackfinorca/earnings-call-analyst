import React from 'react';
import Icon from '../../../components/AppIcon';

const AnticipatedTopics = ({ topics }) => {
  const getTopicIcon = (priority) => {
    switch (priority) {
      case 'high':
        return 'AlertTriangle';
      case 'medium':
        return 'Info';
      case 'low':
        return 'Circle';
      default:
        return 'Circle';
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high':
        return 'text-destructive';
      case 'medium':
        return 'text-warning';
      case 'low':
        return 'text-muted-foreground';
      default:
        return 'text-muted-foreground';
    }
  };

  const getPriorityBg = (priority) => {
    switch (priority) {
      case 'high':
        return 'bg-destructive/10';
      case 'medium':
        return 'bg-warning/10';
      case 'low':
        return 'bg-muted/10';
      default:
        return 'bg-muted/10';
    }
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex items-center space-x-3 mb-6">
        <div className="flex items-center justify-center w-10 h-10 bg-accent/10 rounded-lg">
          <Icon name="MessageSquare" size={20} className="text-accent" strokeWidth={2} />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Anticipated Topics</h3>
          <p className="text-sm text-muted-foreground">Key market expectations for earnings call</p>
        </div>
      </div>
      <div className="space-y-4">
        {topics?.map((topic, index) => (
          <div key={index} className="flex items-start space-x-4 p-4 rounded-lg border border-border hover:bg-muted/30 transition-colors duration-200">
            <div className={`flex items-center justify-center w-8 h-8 rounded-full ${getPriorityBg(topic?.priority)}`}>
              <Icon 
                name={getTopicIcon(topic?.priority)} 
                size={16} 
                className={getPriorityColor(topic?.priority)}
                strokeWidth={2}
              />
            </div>
            
            <div className="flex-1 space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="font-medium text-text-primary">{topic?.title}</h4>
                <span className={`text-xs px-2 py-1 rounded-full capitalize ${getPriorityBg(topic?.priority)} ${getPriorityColor(topic?.priority)}`}>
                  {topic?.priority}
                </span>
              </div>
              
              <p className="text-sm text-muted-foreground leading-relaxed">
                {topic?.description}
              </p>
              
              {topic?.impact && (
                <div className="flex items-center space-x-2 mt-2">
                  <Icon name="TrendingUp" size={14} className="text-accent" strokeWidth={2} />
                  <span className="text-xs text-accent font-medium">
                    Expected Impact: {topic?.impact}
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-6 pt-4 border-t border-border">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Based on {topics?.length} key market indicators</span>
          <div className="flex items-center space-x-1">
            <Icon name="Brain" size={12} strokeWidth={2} />
            <span>AI-generated insights</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnticipatedTopics;