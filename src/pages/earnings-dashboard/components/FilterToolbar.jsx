import React, { useState } from 'react';
import Input from '../../../components/ui/Input';
import Select from '../../../components/ui/Select';
import Button from '../../../components/ui/Button';
import Icon from '../../../components/AppIcon';

const FilterToolbar = ({ 
  searchTerm, 
  onSearchChange, 
  dateRange, 
  onDateRangeChange, 
  sector, 
  onSectorChange,
  onClearFilters,
  sectorOptions = []
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const dateRangeOptions = [
    { value: 'all', label: 'All Dates' },
    { value: '3', label: 'Next 3 Days' },
    { value: '7', label: 'Next 7 Days' },
    { value: '14', label: 'Next 14 Days' },
    { value: '30', label: 'Next 30 Days' }
  ];

  const hasActiveFilters = searchTerm || dateRange !== 'all' || sector !== 'all';

  return (
    <div className="bg-card border border-border rounded-lg p-4 mb-6 shadow-sm">
      {/* Desktop Filter Layout */}
      <div className="hidden md:flex items-center space-x-4">
        <div className="flex-1 max-w-md">
          <Input
            type="search"
            placeholder="Search by company name or ticker..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e?.target?.value)}
            className="w-full"
          />
        </div>

        <div className="w-48">
          <Select
            placeholder="Date Range"
            options={dateRangeOptions}
            value={dateRange}
            onChange={onDateRangeChange}
          />
        </div>

        <div className="w-48">
          <Select
            placeholder="Sector"
            options={sectorOptions}
            value={sector}
            onChange={onSectorChange}
            searchable
          />
        </div>

        {hasActiveFilters && (
          <Button
            variant="outline"
            size="default"
            onClick={onClearFilters}
            iconName="X"
            iconPosition="left"
            iconSize={16}
          >
            Clear
          </Button>
        )}

        <div className="flex items-center text-sm text-text-secondary">
          <Icon name="Filter" size={16} className="mr-1" />
          <span>Filters</span>
        </div>
      </div>
      {/* Mobile Filter Layout */}
      <div className="md:hidden">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-text-primary">Filter Earnings</h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            iconName={isExpanded ? "ChevronUp" : "ChevronDown"}
            iconPosition="right"
            iconSize={16}
          >
            {isExpanded ? 'Hide' : 'Show'} Filters
          </Button>
        </div>

        <div className="mb-4">
          <Input
            type="search"
            placeholder="Search companies..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e?.target?.value)}
            className="w-full"
          />
        </div>

        {isExpanded && (
          <div className="space-y-4 pt-4 border-t border-border">
            <Select
              label="Date Range"
              options={dateRangeOptions}
              value={dateRange}
              onChange={onDateRangeChange}
            />

            <Select
              label="Sector"
              options={sectorOptions}
              value={sector}
              onChange={onSectorChange}
              searchable
            />

            {hasActiveFilters && (
              <Button
                variant="outline"
                size="default"
                onClick={onClearFilters}
                iconName="X"
                iconPosition="left"
                iconSize={16}
                fullWidth
              >
                Clear All Filters
              </Button>
            )}
          </div>
        )}

        {hasActiveFilters && !isExpanded && (
          <div className="flex items-center justify-between pt-2 border-t border-border">
            <div className="flex items-center text-sm text-text-secondary">
              <Icon name="Filter" size={14} className="mr-1" />
              <span>Active filters applied</span>
            </div>
            <Button
              variant="ghost"
              size="xs"
              onClick={onClearFilters}
              iconName="X"
              iconSize={12}
            >
              Clear
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default FilterToolbar;
