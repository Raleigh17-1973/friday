"use client";

import React from "react";

export interface Column<T> {
  key: string;
  label: string;
  render?: (value: unknown, row: T) => React.ReactNode;
  sortable?: boolean;
}

interface DataTableProps<T extends Record<string, unknown>> {
  columns: Column<T>[];
  rows: T[];
  sortable?: boolean;
  emptyLabel?: string;
  paginated?: boolean;
  pageSize?: number;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  emptyLabel = "No data yet.",
  paginated = false,
  pageSize = 20,
}: DataTableProps<T>) {
  const [page, setPage] = React.useState(0);
  const [sortKey, setSortKey] = React.useState<string | null>(null);
  const [sortAsc, setSortAsc] = React.useState(true);

  const sorted = React.useMemo(() => {
    if (!sortKey) return rows;
    return [...rows].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      const cmp = String(av ?? "").localeCompare(String(bv ?? ""), undefined, { numeric: true });
      return sortAsc ? cmp : -cmp;
    });
  }, [rows, sortKey, sortAsc]);

  const paged = paginated ? sorted.slice(page * pageSize, (page + 1) * pageSize) : sorted;
  const totalPages = Math.ceil(sorted.length / pageSize);

  function handleSort(col: Column<T>) {
    if (!col.sortable) return;
    if (sortKey === col.key) {
      setSortAsc((a) => !a);
    } else {
      setSortKey(col.key);
      setSortAsc(true);
    }
  }

  if (rows.length === 0) {
    return <p className="data-table-empty">{emptyLabel}</p>;
  }

  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col)}
                className={col.sortable ? "sortable" : ""}
                aria-sort={
                  sortKey === col.key
                    ? (sortAsc ? "ascending" : "descending")
                    : undefined
                }
              >
                {col.label}
                {col.sortable && sortKey === col.key && (
                  <span aria-hidden className="sort-indicator">{sortAsc ? " ↑" : " ↓"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {paged.map((row, i) => (
            <tr key={i}>
              {columns.map((col) => (
                <td key={col.key}>
                  {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {paginated && totalPages > 1 && (
        <div className="data-table-pagination">
          <button
            className="btn btn-ghost"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            ← Prev
          </button>
          <span className="pagination-info">
            Page {page + 1} of {totalPages}
          </span>
          <button
            className="btn btn-ghost"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((p) => p + 1)}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
