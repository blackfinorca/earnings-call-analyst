import earningsData from "../data/earnings_data.json";

const parseNumber = (value) => {
  if (value === null || value === undefined) return null;
  const cleaned = String(value).trim().replace(/,/g, "");
  if (!cleaned) return null;
  const multipliers = { K: 1e3, M: 1e6, B: 1e9, T: 1e12 };
  const suffix = cleaned.slice(-1).toUpperCase();
  const multiplier = multipliers[suffix];
  if (multiplier) {
    const num = Number(cleaned.slice(0, -1));
    return Number.isFinite(num) ? num * multiplier : null;
  }
  const num = Number(cleaned);
  return Number.isFinite(num) ? num : null;
};

const toIsoDate = (day, time) => {
  if (!day) return null;
  const normalized = (time || '').toLowerCase();
  let isoTime = '21:00:00Z';
  if (normalized.includes('before')) isoTime = '09:00:00Z';
  else if (normalized.includes('after')) isoTime = '21:00:00Z';
  else if (normalized.includes('time not supplied') || normalized === '-' || normalized === '') isoTime = '21:00:00Z';
  return `${day}T${isoTime}`;
};

const flattenDays = (data) => {
  const items = [];
  (data.days || []).forEach((day) => {
    (day.rows || []).forEach((row, index) => {
      const symbol = row?.symbol || row?.ticker || '';
      items.push({
        id: row?.id || `${symbol || 'UNK'}-${day.day}-${index}`,
        ticker: symbol,
        companyName: row?.company || row?.companyName || symbol,
        sector: row?.sector || 'Unknown',
        eventName: row?.eventName || `${row?.company || symbol} Earnings Call`,
        earningsDate: row?.earningsDate || toIsoDate(day.day, row?.time),
        stockPrice:
          typeof row?.stockPrice === 'number'
            ? row.stockPrice
            : parseNumber(row?.stockPrice) || parseNumber(row?.price),
        priceChange: parseNumber(row?.priceChange ?? row?.surprise_pct),
        epsEstimate:
          typeof row?.epsEstimate === 'number'
            ? row.epsEstimate
            : parseNumber(row?.epsEstimate ?? row?.eps_estimate),
        revenueEstimate:
          typeof row?.revenueEstimate === 'number'
            ? row.revenueEstimate
            : parseNumber(row?.revenueEstimate ?? row?.revenue_estimate),
        time: row?.time || 'Time Not Supplied',
        quoteUrl: row?.quote_url || null,
        raw: row,
      });
    });
  });
  return items;
};

export const fetchUpcomingEarnings = async () => flattenDays(earningsData);

export const __testables__ = {
  flattenDays,
  parseNumber,
};
