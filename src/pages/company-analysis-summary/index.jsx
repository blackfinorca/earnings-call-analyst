import React, { useState, useEffect } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import Header from '../../components/ui/Header';
import Breadcrumb from '../../components/ui/Breadcrumb';
import SentimentScore from './components/SentimentScore';
import DataCollectionStatus from './components/DataCollectionStatus';
import AnticipatedTopics from './components/AnticipatedTopics';
import InvestmentRecommendation from './components/InvestmentRecommendation';
import SupportingDataPanel from './components/SupportingDataPanel';
import ActionButtons from './components/ActionButtons';
import LoadingSpinner from '../../components/ui/LoadingSpinner';

const CompanyAnalysisSummary = () => {
  const { ticker } = useParams();
  const location = useLocation();
  const [isLoading, setIsLoading] = useState(true);
  const [analysisData, setAnalysisData] = useState(null);

  // Mock data for the analysis
  const mockAnalysisData = {
    company: {
      ticker: ticker || 'AAPL',
      name: 'Apple Inc.',
      sector: 'Technology',
      earningsDate: '2025-01-30'
    },
    sentiment: {
      sentiment: 'Positive',
      score: 78,
      confidence: 85
    },
    dataCollectionStatus: [
      {
        label: 'Earnings Info Retrieval',
        status: 'completed',
        progress: 100,
        count: null
      },
      {
        label: 'News Aggregation',
        status: 'completed',
        progress: 100,
        count: '12 articles'
      },
      {
        label: 'Stock Data Analysis',
        status: 'in-progress',
        progress: 75,
        count: null
      },
      {
        label: 'AI Processing',
        status: 'pending',
        progress: 0,
        count: null
      }
    ],
    anticipatedTopics: [
      {
        title: 'iPhone 16 Sales Performance',
        description: 'Market expects strong commentary on iPhone 16 adoption rates and holiday season performance, particularly in key markets like China and Europe.',
        priority: 'high',
        impact: 'Revenue +5-8%'
      },
      {
        title: 'Services Revenue Growth',
        description: 'Analysts anticipate updates on App Store, iCloud, and subscription services growth trajectory, especially Apple TV+ and Apple Music subscriber numbers.',
        priority: 'high',
        impact: 'Margin expansion'
      },
      {
        title: 'AI Integration Progress',
        description: 'Discussion around Apple Intelligence rollout, user adoption metrics, and impact on device upgrade cycles expected to be key focus areas.',
        priority: 'medium',
        impact: 'Future growth catalyst'
      },
      {
        title: 'Supply Chain & Margins',
        description: 'Commentary on component costs, manufacturing efficiency improvements, and gross margin outlook amid global economic uncertainties.',
        priority: 'medium',
        impact: 'Profitability impact'
      },
      {
        title: 'Capital Allocation Strategy',
        description: 'Updates on share buyback program, dividend policy, and potential strategic investments or acquisitions in the AI and services space.',
        priority: 'low',
        impact: 'Shareholder returns'
      }
    ],
    recommendation: {
      type: 'Buy',
      confidence: 82,
      targetPrice: 245.00,
      upside: 12.5,
      rationale: `Apple's strong fundamentals, robust services ecosystem, and early AI integration position the company well for continued growth. The iPhone 16 cycle shows promising early adoption, while services revenue provides stable, high-margin income. Despite near-term headwinds in China, the company's innovation pipeline and capital allocation strategy support a positive outlook.`,
      keyFactors: [
        'Strong iPhone 16 adoption with AI features driving upgrade cycle',
        'Services segment showing consistent double-digit growth',
        'Robust balance sheet with $162B in cash and equivalents',
        'Market-leading position in premium smartphone segment',
        'Expanding ecosystem creating customer stickiness'
      ],
      risks: [
        'Regulatory pressure in EU and potential antitrust actions',
        'China market volatility and geopolitical tensions',
        'Increased competition in AI and services markets',
        'Potential margin pressure from component cost inflation'
      ]
    },
    stockData: {
      currentPrice: 217.85,
      priceChange: 2.45,
      priceChangePercent: 1.14,
      volume: 45200000,
      avgVolume: 52800000,
      volumeChange: -7600000,
      volumeChangePercent: -14.4,
      epsEstimate: 2.35,
      prevEps: 2.18,
      epsChange: 0.17,
      epsChangePercent: 7.8,
      revenueEstimate: 124500000000,
      prevRevenue: 117200000000,
      revenueChange: 7300000000,
      revenueChangePercent: 6.2,
      marketCap: 3280000000000,
      peRatio: 28.5,
      yearHigh: 237.23,
      yearLow: 164.08
    }
  };

  const breadcrumbItems = [
    { label: 'Dashboard', path: '/earnings-dashboard' },
    { label: 'Company Analysis', path: '/company-analysis-summary' },
    { label: `${mockAnalysisData?.company?.name} (${mockAnalysisData?.company?.ticker})` }
  ];

  useEffect(() => {
    // Simulate data loading
    const loadAnalysisData = async () => {
      setIsLoading(true);
      
      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      setAnalysisData(mockAnalysisData);
      setIsLoading(false);
    };

    loadAnalysisData();
  }, [ticker]);

  const handleAnalyzeAnother = () => {
    // This would typically open a company search modal or redirect to dashboard
    console.log('Analyze another company clicked');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="pt-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="flex items-center justify-center min-h-[60vh]">
              <LoadingSpinner 
                size="xl" 
                text="Generating comprehensive analysis..." 
                className="text-center"
              />
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (!analysisData) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="pt-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="text-center py-12">
              <h2 className="text-2xl font-semibold text-text-primary mb-4">
                Analysis Not Available
              </h2>
              <p className="text-muted-foreground mb-6">
                Unable to load analysis data for the requested company.
              </p>
              <ActionButtons onAnalyzeAnother={handleAnalyzeAnother} />
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Breadcrumb items={breadcrumbItems} />
          
          {/* Company Header */}
          <div className="mb-8">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h1 className="text-3xl font-bold text-text-primary">
                  {analysisData?.company?.name}
                </h1>
                <div className="flex items-center space-x-4 mt-2 text-sm text-muted-foreground">
                  <span className="font-medium">{analysisData?.company?.ticker}</span>
                  <span>•</span>
                  <span>{analysisData?.company?.sector}</span>
                  <span>•</span>
                  <span>Earnings: {new Date(analysisData.company.earningsDate)?.toLocaleDateString()}</span>
                </div>
              </div>
              <div className="mt-4 sm:mt-0">
                <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
                  Pre-Earnings Analysis
                </div>
              </div>
            </div>
          </div>

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column - Primary Content */}
            <div className="lg:col-span-2 space-y-8">
              {/* Sentiment Score - Prominent Display */}
              <SentimentScore 
                sentiment={analysisData?.sentiment?.sentiment}
                score={analysisData?.sentiment?.score}
                confidence={analysisData?.sentiment?.confidence}
              />

              {/* Data Collection Status */}
              <DataCollectionStatus statusData={analysisData?.dataCollectionStatus} />

              {/* Anticipated Topics */}
              <AnticipatedTopics topics={analysisData?.anticipatedTopics} />

              {/* Investment Recommendation */}
              <InvestmentRecommendation recommendation={analysisData?.recommendation} />
            </div>

            {/* Right Column - Supporting Data & Actions */}
            <div className="space-y-8">
              {/* Supporting Data Panel */}
              <SupportingDataPanel stockData={analysisData?.stockData} />

              {/* Action Buttons */}
              <ActionButtons onAnalyzeAnother={handleAnalyzeAnother} />
            </div>
          </div>

          {/* Footer Disclaimer */}
          <div className="mt-12 pt-8 border-t border-border">
            <div className="bg-muted/30 rounded-lg p-4">
              <p className="text-xs text-muted-foreground leading-relaxed">
                <strong>Disclaimer:</strong> This analysis is generated using AI and should not be considered as financial advice. 
                All data is sourced from public APIs and news aggregation. Past performance does not guarantee future results. 
                Please consult with a qualified financial advisor before making investment decisions. 
                Stock prices and estimates are subject to market volatility and may change rapidly.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default CompanyAnalysisSummary;