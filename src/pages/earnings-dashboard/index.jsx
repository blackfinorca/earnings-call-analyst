import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import Header from '../../components/ui/Header';
import Breadcrumb from '../../components/ui/Breadcrumb';
import FilterToolbar from './components/FilterToolbar';
import EarningsTable from './components/EarningsTable';
import PaginationControls from './components/PaginationControls';
import DashboardStats from './components/DashboardStats';
import Icon from '../../components/AppIcon';
import { fetchUpcomingEarnings } from '../../utils/dataClient';

const startOfDay = (value) => {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  return date;
};

const endOfDay = (value) => {
  const date = new Date(value);
  date.setHours(23, 59, 59, 999);
  return date;
};

const addDays = (value, days) => {
  const date = new Date(value);
  date.setDate(date.getDate() + days);
  return date;
};


const EarningsDashboard = () => {
  const navigate = useNavigate();

  // State management
  const [earningsData, setEarningsData] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [dateRange, setDateRange] = useState('all');
  const [sector, setSector] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(25);
  const [sortConfig, setSortConfig] = useState({ key: 'earningsDate', direction: 'asc' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Breadcrumb items
  const breadcrumbItems = [
    { label: 'Dashboard', path: '/earnings-dashboard' }
  ];

  const getSectorSlug = (value) => {
    if (!value) return 'unknown';
    return value.toLowerCase().replace(/\s+/g, '-');
  };

  const sectorOptions = useMemo(() => {
    const sectors = new Set();
    earningsData.forEach((item) => {
      if (item?.sector) {
        sectors.add(item.sector);
      }
    });

    const sorted = Array.from(sectors)
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b));

    return [
      { value: 'all', label: 'All Sectors' },
      ...sorted.map((label) => ({
        label,
        value: getSectorSlug(label)
      }))
    ];
  }, [earningsData]);

  // Filter and sort data
  const filteredAndSortedData = useMemo(() => {
    let filtered = [...earningsData];

    // Apply search filter
    if (searchTerm) {
      const searchLower = searchTerm?.toLowerCase();
      filtered = filtered?.filter(item => 
        item?.ticker?.toLowerCase()?.includes(searchLower) ||
        item?.companyName?.toLowerCase()?.includes(searchLower)
      );
    }

    // Apply date range filter
    if (dateRange !== 'all') {
      const todayStart = startOfDay(new Date());
      const daysAhead = parseInt(dateRange);
      const cutoffDate = endOfDay(addDays(todayStart, daysAhead));

      filtered = filtered?.filter(item => {
        const earningsDate = startOfDay(item.earningsDate);
        return earningsDate >= todayStart && earningsDate <= cutoffDate;
      });
    }

    // Apply sector filter
    if (sector !== 'all') {
      filtered = filtered?.filter(item => 
        getSectorSlug(item?.sector) === sector
      );
    }

    // Apply sorting
    filtered?.sort((a, b) => {
      let aValue = a?.[sortConfig?.key];
      let bValue = b?.[sortConfig?.key];

      // Handle date sorting
      if (sortConfig?.key === 'earningsDate') {
        aValue = new Date(aValue);
        bValue = new Date(bValue);
      }

      // Handle string sorting
      if (typeof aValue === 'string') {
        aValue = aValue?.toLowerCase();
        bValue = bValue?.toLowerCase();
      }

      if (aValue < bValue) {
        return sortConfig?.direction === 'asc' ? -1 : 1;
      }
      if (aValue > bValue) {
        return sortConfig?.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });

    return filtered;
  }, [earningsData, searchTerm, dateRange, sector, sortConfig]);

  // Calculate pagination
  const totalItems = filteredAndSortedData?.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedData = filteredAndSortedData?.slice(startIndex, startIndex + itemsPerPage);

  // Calculate dashboard stats
  const dashboardStats = useMemo(() => {
    const todayStart = startOfDay(new Date());
    const oneWeekEnd = endOfDay(addDays(todayStart, 7));
    const twoWeeksEnd = endOfDay(addDays(todayStart, 14));

    const thisWeek = earningsData?.filter(item => {
      const earningsDate = startOfDay(item.earningsDate);
      return earningsDate >= todayStart && earningsDate <= oneWeekEnd;
    })?.length;

    const nextWeek = earningsData?.filter(item => {
      const earningsDate = startOfDay(item.earningsDate);
      return earningsDate > oneWeekEnd && earningsDate <= twoWeeksEnd;
    })?.length;

    const sectors = new Set(earningsData.map(item => item.sector))?.size;

    return {
      total: earningsData?.length,
      thisWeek,
      nextWeek,
      sectors
    };
  }, [earningsData]);

  // Event handlers
  const handleSort = (key) => {
    setSortConfig(prevConfig => ({
      key,
      direction: prevConfig?.key === key && prevConfig?.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const handleGenerate = (earning) => {
    navigate(`/company-analysis-summary?ticker=${earning?.ticker}&company=${encodeURIComponent(earning?.companyName)}`);
  };

  const handleClearFilters = () => {
    setSearchTerm('');
    setDateRange('all');
    setSector('all');
    setCurrentPage(1);
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleItemsPerPageChange = (newItemsPerPage) => {
    setItemsPerPage(newItemsPerPage);
    setCurrentPage(1);
  };

  // Fetch earnings data from Yahoo Finance API
  useEffect(() => {
    let isMounted = true;

    const loadData = async () => {
      setLoading(true);
      setError(null);

      try {
        const dataset = await fetchUpcomingEarnings();
        if (isMounted) {
          if (!dataset || dataset.length === 0) {
            setError('No earnings data available in the local cache.');
          } else {
            setError(null);
          }
          const enriched = (dataset || []).map((item, index) => ({
            ...item,
            id: item.id || `${item.ticker}-${index}`
          }));
          setEarningsData(enriched);
        }
      } catch (err) {
        if (isMounted) {
          setError('Unable to load earnings data from the local JSON file. Please regenerate it.');
          setEarningsData([]);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadData();

    return () => {
      isMounted = false;
    };
  }, []);

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, dateRange, sector]);

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Page Header */}
          <div className="mb-8">
            <Breadcrumb items={breadcrumbItems} />
            
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-text-primary mb-2">
                  Earnings Dashboard
                </h1>
                <p className="text-text-secondary">
                  Discover and analyze upcoming earnings calls for informed investment decisions
                </p>
              </div>
              
              <div className="hidden md:flex items-center space-x-2 text-sm text-text-secondary">
                <Icon name="Clock" size={16} />
                <span>Last updated: {new Date()?.toLocaleTimeString()}</span>
              </div>
            </div>
          </div>

          {/* Dashboard Stats */}
          <DashboardStats stats={dashboardStats} loading={loading} />

          {/* Filter Toolbar */}
          <FilterToolbar
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            sector={sector}
            onSectorChange={setSector}
            sectorOptions={sectorOptions}
            onClearFilters={handleClearFilters}
          />

          {/* Error State */}
          {error && (
            <div className="mb-6 rounded-lg border border-destructive/20 bg-destructive/10 text-destructive px-4 py-3 text-sm">
              {error}
            </div>
          )}

          {/* Results Summary */}
          {!loading && (
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm text-text-secondary">
                {totalItems === 0 ? (
                  'No earnings calls found'
                ) : (
                  `Showing ${startIndex + 1}-${Math.min(startIndex + itemsPerPage, totalItems)} of ${totalItems} earnings calls`
                )}
              </div>
              
              {totalItems > 0 && (
                <div className="flex items-center space-x-2 text-sm text-text-secondary">
                  <Icon name="ArrowUpDown" size={14} />
                  <span>Sorted by {sortConfig?.key} ({sortConfig?.direction})</span>
                </div>
              )}
            </div>
          )}

          {/* Earnings Table */}
          <EarningsTable
            earnings={paginatedData}
            sortConfig={sortConfig}
            onSort={handleSort}
            onGenerate={handleGenerate}
            loading={loading}
          />

          {/* Pagination */}
          {!loading && totalPages > 1 && (
            <PaginationControls
              currentPage={currentPage}
              totalPages={totalPages}
              totalItems={totalItems}
              itemsPerPage={itemsPerPage}
              onPageChange={handlePageChange}
              onItemsPerPageChange={handleItemsPerPageChange}
              loading={loading}
            />
          )}
        </div>
      </main>
    </div>
  );
};

export default EarningsDashboard;
