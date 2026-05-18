"use client";

import type { Script } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

export function ScriptGrid({ script }: { script: Script }) {
  const updateCell = useAppStore((state) => state.updateCell);
  const columns = [...script.columns].sort((a, b) => a.order - b.order);
  const rows = [...script.rows].sort((a, b) => a.order - b.order);

  return (
    <div className="scriptGridWrap">
      <table className="scriptGrid">
        <thead>
          <tr>
            <th className="indexCell">#</th>
            {columns.map((column) => (
              <th key={column.column_id}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={row.row_id}>
              <td className="indexCell">{rowIndex + 1}</td>
              {columns.map((column) => {
                const cell = row.cells.find((item) => item.column_id === column.column_id);
                const value = cell?.value ?? "";
                return (
                  <td key={column.column_id}>
                    {column.multiline ? (
                      <textarea
                        value={value}
                        onChange={(event) => updateCell(row.row_id, column.column_id, event.target.value)}
                      />
                    ) : (
                      <input
                        value={value}
                        onChange={(event) => updateCell(row.row_id, column.column_id, event.target.value)}
                      />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

