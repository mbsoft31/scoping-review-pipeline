import React, { useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  ColumnDef,
} from '@tanstack/react-table';
import { Link } from '@tanstack/react-router';
import type { Post } from '../pages/PostsPage';

/**
 * Table component that uses TanStack Table to render a list of posts.
 * Clicking the title navigates to the post details page using
 * TanStack Router's ``Link`` component.
 */
export interface PostsTableProps {
  posts: Post[];
}

const PostsTable: React.FC<PostsTableProps> = ({ posts }) => {
  // Define table columns.  Each column has an accessor and a cell renderer.
  const columns = useMemo<ColumnDef<Post>[]>(
    () => [
      {
        header: 'ID',
        accessorKey: 'id',
        cell: (info) => info.getValue(),
      },
      {
        header: 'Title',
        accessorKey: 'title',
        cell: (info) => {
          const post = info.row.original;
          return (
            <Link
              to={`/posts/${post.id}`}
              className="text-blue-600 hover:underline"
            >
              {info.getValue() as string}
            </Link>
          );
        },
      },
      {
        header: 'Body',
        accessorKey: 'body',
        cell: (info) => (
          <span className="truncate block max-w-xs" title={info.getValue() as string}>
            {(info.getValue() as string).substring(0, 50)}…
          </span>
        ),
      },
    ],
    [],
  );

  const table = useReactTable({
    data: posts,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  scope="col"
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="hover:bg-gray-100">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-4 py-2 whitespace-nowrap">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default PostsTable;