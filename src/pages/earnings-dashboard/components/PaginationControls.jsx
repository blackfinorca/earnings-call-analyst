import React from 'react';
import Button from '../../../components/ui/Button';
import Select from '../../../components/ui/Select';


const PaginationControls = ({
  currentPage,
  totalPages,
  totalItems,
  itemsPerPage,
  onPageChange,
  onItemsPerPageChange,
  loading
}) => {
  const itemsPerPageOptions = [
    { value: 10, label: '10 per page' },
    { value: 25, label: '25 per page' },
    { value: 50, label: '50 per page' },
    { value: 100, label: '100 per page' }
  ];

  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);

  const getVisiblePages = () => {
    const delta = 2;
    const range = [];
    const rangeWithDots = [];

    for (let i = Math.max(2, currentPage - delta); i <= Math.min(totalPages - 1, currentPage + delta); i++) {
      range?.push(i);
    }

    if (currentPage - delta > 2) {
      rangeWithDots?.push(1, '...');
    } else {
      rangeWithDots?.push(1);
    }

    rangeWithDots?.push(...range);

    if (currentPage + delta < totalPages - 1) {
      rangeWithDots?.push('...', totalPages);
    } else if (totalPages > 1) {
      rangeWithDots?.push(totalPages);
    }

    return rangeWithDots;
  };

  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className="bg-card border border-border rounded-lg p-4 mt-6">
      <div className="flex flex-col md:flex-row items-center justify-between space-y-4 md:space-y-0">
        {/* Items per page selector */}
        <div className="flex items-center space-x-3">
          <span className="text-sm text-text-secondary">Show:</span>
          <div className="w-32">
            <Select
              options={itemsPerPageOptions}
              value={itemsPerPage}
              onChange={onItemsPerPageChange}
              disabled={loading}
            />
          </div>
        </div>

        {/* Page info */}
        <div className="text-sm text-text-secondary">
          Showing {startItem}-{endItem} of {totalItems} results
        </div>

        {/* Pagination controls */}
        <div className="flex items-center space-x-1">
          {/* Previous button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage === 1 || loading}
            iconName="ChevronLeft"
            iconSize={16}
          >
            Previous
          </Button>

          {/* Page numbers - Desktop */}
          <div className="hidden md:flex items-center space-x-1 mx-2">
            {getVisiblePages()?.map((page, index) => (
              <React.Fragment key={index}>
                {page === '...' ? (
                  <span className="px-3 py-2 text-text-secondary">...</span>
                ) : (
                  <Button
                    variant={currentPage === page ? "default" : "ghost"}
                    size="sm"
                    onClick={() => onPageChange(page)}
                    disabled={loading}
                    className="min-w-[40px]"
                  >
                    {page}
                  </Button>
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Page numbers - Mobile */}
          <div className="md:hidden flex items-center space-x-2 mx-2">
            <span className="text-sm text-text-secondary">
              Page {currentPage} of {totalPages}
            </span>
          </div>

          {/* Next button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage === totalPages || loading}
            iconName="ChevronRight"
            iconPosition="right"
            iconSize={16}
          >
            Next
          </Button>
        </div>
      </div>
      {/* Quick jump - Desktop only */}
      <div className="hidden lg:flex items-center justify-center mt-4 pt-4 border-t border-border">
        <div className="flex items-center space-x-2">
          <span className="text-sm text-text-secondary">Jump to page:</span>
          <div className="flex items-center space-x-1">
            <Button
              variant="ghost"
              size="xs"
              onClick={() => onPageChange(1)}
              disabled={currentPage === 1 || loading}
              iconName="ChevronsLeft"
              iconSize={14}
            >
              First
            </Button>
            <Button
              variant="ghost"
              size="xs"
              onClick={() => onPageChange(totalPages)}
              disabled={currentPage === totalPages || loading}
              iconName="ChevronsRight"
              iconSize={14}
            >
              Last
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PaginationControls;