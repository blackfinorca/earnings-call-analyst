import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useSearchParams, useNavigate } from 'react-router-dom';
import Header from '../../components/ui/Header';
import Breadcrumb from '../../components/ui/Breadcrumb';
import SentimentScore from './components/SentimentScore';
import DataCollectionStatus from './components/DataCollectionStatus';
import AnticipatedTopics from './components/AnticipatedTopics';
import InvestmentRecommendation from './components/InvestmentRecommendation';
import SupportingDataPanel from './components/SupportingDataPanel';
import ActionButtons from './components/ActionButtons';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import { fetchUpcomingEarnings } from '../../utils/dataClient';

const DEFAULT_SENTIMENT = {
  sentiment: 'Neutral',
  score: 50,
  confidence: 70
};

const DEFAULT_DATA_STATUS = [
  {
    label: 'Earnings Calendar',
    status: 'completed',
    progress: 100,
    count: null
  },
  {
    label: 'Quote Snapshot',
    status: 'completed',
    progress: 100,
    count: null
  },
  {
    label: 'AI Processing',
    status: 'in-progress',
    progress: 60,
    count: null
  },
  {
    label: 'News Aggregation',
    status: 'pending',
    progress: 0,
    count: null
  }
];

const DEFAULT_TOPICS = [
  {
    title: 'Upcoming Earnings Call Themes',
    description: 'Monitor management commentary on revenue guidance, margin outlook, and capital allocation strategy.',
    priority: 'medium',
    impact: 'Guidance clarity'
  },
  {
    title: 'Macro Environment',
    description: 'Assess how macroeconomic conditions and consumer spending trends are impacting results.',
    priority: 'medium',
    impact: 'Risk sensitivity'
  },
  {
    title: 'Product Pipeline Updates',
    description: 'Look for updates on new products or services that could influence long-term growth.',
    priority: 'low',
    impact: 'Innovation visibility'
  }
];

const DEFAULT_RECOMMENDATION = {
  type: 'Hold',
  confidence: 55,
  targetPrice: null,
  upside: null,
  rationale:
    'Automation has generated this snapshot based on available earnings calendar information. Please supplement with fundamental and technical research before making investment decisions.',
  keyFactors: [
    'Upcoming earnings event scheduled in the selected window',
    'Latest price, EPS estimate, and revenue estimate pulled from RapidAPI',
    'Quantitative metrics updated from cached data'
  ],
  risks: [
    'Limited qualitative insight without manual research',
    'Macro and sector forces may change between refreshes',
    'Automated data may lag real-time market developments'
  ]
};

const toDisplayDate = (isoString) => {
  if (!isoString) return 'TBA';
  try {
    const date = new Date(isoString);
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  } catch {
    return isoString;
  }
};

const formatNumber = (value) => {
  if (value === null || value === undefined) return 'N/A';
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(2)}K`;
  return value.toFixed ? value.toFixed(2) : value;
};

const CompanyAnalysisSummary = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const queryTicker = (searchParams.get('ticker') || '').toUpperCase();
  const [isLoading, setIsLoading] = useState(true);
  const [analysisData, setAnalysisData] = useState(null);

  useEffect(() => {
    let isMounted = true;

    const loadData = async () => {
      setIsLoading(true);
      try {
        const entries = await fetchUpcomingEarnings();
        if (!isMounted) return;

        const match =
          entries.find((item) => item.ticker?.toUpperCase() === queryTicker) ||
          entries[0];

        if (!match) {
          setAnalysisData(null);
          setIsLoading(false);
          return;
        }

        const companyName = match.companyName || match.company || match.ticker || 'Unknown Company';
        const tickerSymbol = match.ticker || queryTicker;

        const stockData = {
          currentPrice: match.stockPrice ?? null,
          tradingVolume: match.tradingVolume ?? null,
          epsEstimate: match.epsEstimate ?? null,
          revenueEstimate: match.revenueEstimate ?? null,
          priceChange: match.priceChange ?? null,
          marketCap: match.marketCap ?? null,
          peRatio: match.peRatio ?? null,
          yearHigh: match.yearHigh ?? null,
          yearLow: match.yearLow ?? null
        };

        const preparedData = {
          company: {
            ticker: tickerSymbol,
            name: companyName,
            sector: match.sector || 'Unknown Sector',
            earningsDate: match.earningsDate || match.day
          },
          sentiment: DEFAULT_SENTIMENT,
          dataCollectionStatus: DEFAULT_DATA_STATUS,
          anticipatedTopics: DEFAULT_TOPICS,
          recommendation: DEFAULT_RECOMMENDATION,
          stockData
        };

        setAnalysisData(preparedData);
      } catch (error) {
        console.error('Failed to load company analysis data', error);
        if (isMounted) {
          setAnalysisData(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    loadData();

    return () => {
      isMounted = false;
    };
  }, [queryTicker, location.search]);

  const breadcrumbItems = useMemo(() => {
    const companyName = analysisData?.company?.name || 'Company Analysis';
    const ticker = analysisData?.company?.ticker ? `(${analysisData.company.ticker})` : '';
    return [
      { label: 'Dashboard', path: '/earnings-dashboard' },
      { label: 'Company Analysis', path: '/company-analysis-summary' },
      { label: `${companyName} ${ticker}`.trim() }
    ];
  }, [analysisData]);

  const handleAnalyzeAnother = () => {
    navigate('/earnings-dashboard');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="pt-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="flex items-center justify-center min-h-[60vh]">
              <LoadingSpinner size="xl" text="Loading company snapshot..." className="text-center" />
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

          <div className="mb-8">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h1 className="text-3xl font-bold text-text-primary">
                  {analysisData.company.name}
                </h1>
                <div className="flex items-center space-x-4 mt-2 text-sm text-muted-foreground">
                  <span className="font-medium">{analysisData.company.ticker}</span>
                  <span>•</span>
                  <span>{analysisData.company.sector}</span>
                  <span>•</span>
                  <span>
                    Earnings: {toDisplayDate(analysisData.company.earningsDate)}
                  </span>
                </div>
              </div>
              <div className="mt-4 sm:mt-0">
                <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
                  Automated Snapshot
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-8">
              <SentimentScore
                sentiment={analysisData.sentiment.sentiment}
                score={analysisData.sentiment.score}
                confidence={analysisData.sentiment.confidence}
              />

              <DataCollectionStatus statusData={analysisData.dataCollectionStatus} />

              <AnticipatedTopics topics={analysisData.anticipatedTopics} />

              <InvestmentRecommendation recommendation={analysisData.recommendation} />
            </div>

            <div className="space-y-8">
              <SupportingDataPanel
                stockData={{
                  currentPrice: analysisData.stockData.currentPrice,
                  priceChange: analysisData.stockData.priceChange,
                  priceChangePercent: null,
                  volume: analysisData.stockData.tradingVolume,
                  avgVolume: null,
                  volumeChange: null,
                  volumeChangePercent: null,
                  epsEstimate: analysisData.stockData.epsEstimate,
                  prevEps: null,
                  epsChange: null,
                  epsChangePercent: null,
                  revenueEstimate: analysisData.stockData.revenueEstimate,
                  prevRevenue: null,
                  revenueChange: null,
                  revenueChangePercent: null,
                  marketCap: null,
                  peRatio: null,
                  yearHigh: null,
                  yearLow: null
                }}
                formatNumber={formatNumber}
              />

              <ActionButtons onAnalyzeAnother={handleAnalyzeAnother} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default CompanyAnalysisSummary;
