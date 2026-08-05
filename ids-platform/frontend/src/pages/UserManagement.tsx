import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authService } from "../services/authService";
import type { CurrentUser } from "../types/auth";

export function UserManagement() {
  const queryClient = useQueryClient();
  const [editingUser, setEditingUser] = useState<string | null>(null);
  const [selectedRole, setSelectedRole] = useState<string>("");

  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: authService.getUsers,
  });

  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: authService.listRoles,
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ username, role }: { username: string; role: string }) =>
      authService.updateUserRole(username, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setEditingUser(null);
    },
  });

  const toggleStatusMutation = useMutation({
    mutationFn: ({ username, deactivate }: { username: string; deactivate: boolean }) =>
      authService.toggleUserStatus(username, deactivate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const handleRoleChange = (user: CurrentUser) => {
    if (selectedRole && selectedRole !== user.role) {
      updateRoleMutation.mutate({ username: user.username, role: selectedRole });
    } else {
      setEditingUser(null);
    }
  };

  return (
    <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">User Management</h1>
          <p className="text-gray-400 mt-2">
            Manage system access, roles, and account status.
          </p>
        </div>

        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-300">
              <thead className="bg-gray-900/50 text-xs uppercase text-gray-400 border-b border-gray-700">
                <tr>
                  <th className="px-6 py-4 font-medium">Username</th>
                  <th className="px-6 py-4 font-medium">Email</th>
                  <th className="px-6 py-4 font-medium">Role</th>
                  <th className="px-6 py-4 font-medium">Status</th>
                  <th className="px-6 py-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {usersQuery.isLoading ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                      Loading users...
                    </td>
                  </tr>
                ) : usersQuery.data?.map((user) => (
                  <tr key={user.username} className="hover:bg-gray-700/50 transition-colors">
                    <td className="px-6 py-4 font-medium text-slate-100">{user.username}</td>
                    <td className="px-6 py-4">{user.email || "—"}</td>
                    <td className="px-6 py-4">
                      {editingUser === user.username ? (
                        <select
                          value={selectedRole}
                          onChange={(e) => setSelectedRole(e.target.value)}
                          className="bg-gray-900 border border-gray-700 rounded-lg px-2 py-1 text-sm text-slate-100"
                        >
                          {rolesQuery.data?.map((role) => (
                            <option key={role.name} value={role.name}>
                              {role.name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
                          {user.role}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {user.is_active ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right space-x-3">
                      {editingUser === user.username ? (
                        <button
                          onClick={() => handleRoleChange(user)}
                          className="text-green-400 hover:text-green-300 font-medium"
                        >
                          Save
                        </button>
                      ) : (
                        <button
                          onClick={() => {
                            setEditingUser(user.username);
                            setSelectedRole(user.role);
                          }}
                          className="text-blue-400 hover:text-blue-300 font-medium"
                        >
                          Change Role
                        </button>
                      )}
                      <button
                        onClick={() => toggleStatusMutation.mutate({ username: user.username, deactivate: user.is_active })}
                        className={`${user.is_active ? 'text-red-400 hover:text-red-300' : 'text-green-400 hover:text-green-300'} font-medium`}
                      >
                        {user.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
    </div>
  );
}
