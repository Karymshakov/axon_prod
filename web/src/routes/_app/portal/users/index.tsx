import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import {
  PlusIcon, SearchIcon, MoreHorizontalIcon,
  UsersIcon, UserCheckIcon, ShieldIcon, ChevronUpIcon, ChevronDownIcon,
} from 'lucide-react'
import {
  getAdminStats, getAdminUsers, createAdminUser, updateAdminUser, deleteAdminUser,
  type AdminUser, type AdminUsersParams, USER_ROLE_LABELS, type UserRole,
} from '@/lib/api'
import { useLanguage } from '@/contexts/language-context'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from '@/components/ui/form'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Skeleton } from '@/components/ui/skeleton'

export const Route = createFileRoute('/_app/portal/users/')({
  validateSearch: (search) => ({
    search: (search.search as string) || '',
    role: (search.role as string) || '',
    status: (search.status as string) || '',
    ordering: (search.ordering as string) || '-created_at',
  }),
  component: AdminUsersPage,
})

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'admin', label: 'Admin / Manager' },
  { value: 'support', label: 'Support' },
  { value: 'tax_accountant', label: 'Tax Accountant' },
]

const createSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  email: z.string().email('Enter a valid email'),
  role: z.enum(['admin', 'support', 'tax_accountant']),
  is_active: z.boolean(),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

const editSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  email: z.string().email('Enter a valid email'),
  role: z.enum(['admin', 'support', 'tax_accountant']),
  is_active: z.boolean(),
})

type CreateFormData = z.infer<typeof createSchema>
type EditFormData = z.infer<typeof editSchema>

function getInitials(name: string, email: string) {
  if (name.trim()) {
    return name.trim().split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase()
  }
  return email[0].toUpperCase()
}

function roleBadgeVariant(role: UserRole): 'default' | 'secondary' | 'outline' {
  if (role === 'admin') return 'default'
  if (role === 'support') return 'secondary'
  return 'outline'
}

function SortableHead({ label, field, ordering, onSort }: {
  label: string; field: string; ordering: string; onSort: (f: string) => void
}) {
  const isAsc = ordering === field
  const isDesc = ordering === `-${field}`
  return (
    <TableHead
      className="cursor-pointer select-none hover:text-foreground"
      onClick={() => onSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {isAsc && <ChevronUpIcon className="h-3 w-3" />}
        {isDesc && <ChevronDownIcon className="h-3 w-3" />}
        {!isAsc && !isDesc && <span className="h-3 w-3" />}
      </span>
    </TableHead>
  )
}

function AdminUsersPage() {
  const { t } = useLanguage()
  const searchParams = Route.useSearch()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { search, role, status, ordering } = searchParams
  const [searchInput, setSearchInput] = useState(search)
  const [userToDelete, setUserToDelete] = useState<AdminUser | null>(null)
  const [userToEdit, setUserToEdit] = useState<AdminUser | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => {
      if (searchInput !== search) updateFilters({ search: searchInput })
    }, 300)
    return () => clearTimeout(t)
  }, [searchInput])

  const updateFilters = (updates: Partial<AdminUsersParams & { ordering: string }>) => {
    navigate({ to: '/portal/users', search: { ...searchParams, ...updates } })
  }

  const toggleSort = (field: string) => {
    const newOrdering = ordering === field ? `-${field}` : field
    updateFilters({ ordering: newOrdering })
  }

  const { data: stats } = useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: getAdminStats,
  })

  const { data: users, status: usersStatus } = useQuery({
    queryKey: ['admin', 'users', search, role, status, ordering],
    queryFn: () => getAdminUsers({ search, role, status, ordering }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteAdminUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin'] })
      toast.success(t('portal.userDeleted'))
      setUserToDelete(null)
    },
    onError: (err: unknown) => {
      const msg = (err as { data?: { detail?: string } })?.data?.detail || t('portal.deleteError')
      toast.error(msg)
      setUserToDelete(null)
    },
  })

  // Create form
  const createForm = useForm<CreateFormData>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: '', email: '', role: 'support', is_active: true, password: '' },
  })

  const createMutation = useMutation({
    mutationFn: createAdminUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin'] })
      toast.success(t('portal.userCreated'))
      setShowCreate(false)
      createForm.reset()
    },
    onError: (err: unknown) => {
      const data = (err as { data?: Record<string, string[]> })?.data
      if (data?.email) {
        createForm.setError('email', { message: data.email[0] })
      } else {
        toast.error(t('portal.createError'))
      }
    },
  })

  // Edit form
  const editForm = useForm<EditFormData>({
    resolver: zodResolver(editSchema),
    defaultValues: { name: '', email: '', role: 'support', is_active: true },
  })

  useEffect(() => {
    if (userToEdit) {
      editForm.reset({
        name: userToEdit.name,
        email: userToEdit.email,
        role: userToEdit.role,
        is_active: userToEdit.is_active,
      })
    }
  }, [userToEdit])

  const editMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: EditFormData }) => updateAdminUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin'] })
      toast.success(t('portal.userUpdated'))
      setUserToEdit(null)
    },
    onError: () => toast.error(t('portal.updateError')),
  })

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
        {/* Header */}
        <div className="px-4 lg:px-6 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Admin Portal</h1>
            <p className="text-muted-foreground text-sm mt-0.5">{t('portal.manageDesc')}</p>
          </div>
          <Button onClick={() => setShowCreate(true)}>
            <PlusIcon className="h-4 w-4 mr-2" />
            {t('portal.addNewUser')}
          </Button>
        </div>

        {/* Stats cards */}
        <div className="px-4 lg:px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card className="border-l-4 border-l-blue-500">
              <CardContent className="px-4 pt-4 pb-4">
                <div className="flex items-start justify-between mb-3">
                  <span className="text-xs font-medium text-muted-foreground">{t('portal.totalUsers')}</span>
                  <div className="h-7 w-7 rounded-md bg-blue-50 dark:bg-blue-950 flex items-center justify-center shrink-0">
                    <UsersIcon className="h-3.5 w-3.5 text-blue-500" />
                  </div>
                </div>
                <p className="text-2xl font-bold">{stats?.total_users ?? '—'}</p>
              </CardContent>
            </Card>
            <Card className="border-l-4 border-l-emerald-500">
              <CardContent className="px-4 pt-4 pb-4">
                <div className="flex items-start justify-between mb-3">
                  <span className="text-xs font-medium text-muted-foreground">{t('portal.activeCount')}</span>
                  <div className="h-7 w-7 rounded-md bg-emerald-50 dark:bg-emerald-950 flex items-center justify-center shrink-0">
                    <UserCheckIcon className="h-3.5 w-3.5 text-emerald-500" />
                  </div>
                </div>
                <p className="text-2xl font-bold">{stats?.active_users ?? '—'}</p>
              </CardContent>
            </Card>
            <Card className="border-l-4 border-l-violet-500">
              <CardContent className="px-4 pt-4 pb-4">
                <div className="flex items-start justify-between mb-3">
                  <span className="text-xs font-medium text-muted-foreground">{t('portal.adminsCount')}</span>
                  <div className="h-7 w-7 rounded-md bg-violet-50 dark:bg-violet-950 flex items-center justify-center shrink-0">
                    <ShieldIcon className="h-3.5 w-3.5 text-violet-500" />
                  </div>
                </div>
                <p className="text-2xl font-bold">{stats?.role_breakdown?.admin ?? '—'}</p>
              </CardContent>
            </Card>
            <Card className="border-l-4 border-l-orange-500">
              <CardContent className="px-4 pt-4 pb-4">
                <div className="flex items-start justify-between mb-3">
                  <span className="text-xs font-medium text-muted-foreground">{t('portal.newThisMonth')}</span>
                  <div className="h-7 w-7 rounded-md bg-orange-50 dark:bg-orange-950 flex items-center justify-center shrink-0">
                    <UsersIcon className="h-3.5 w-3.5 text-orange-500" />
                  </div>
                </div>
                <p className="text-2xl font-bold">{stats?.new_this_month ?? '—'}</p>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Filters */}
        <div className="px-4 lg:px-6 flex flex-wrap gap-2">
          <div className="relative flex-1 min-w-48">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t('portal.searchPlaceholder')}
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={role || 'all'} onValueChange={v => updateFilters({ role: v === 'all' ? '' : v })}>
            <SelectTrigger className="w-44">
              <SelectValue placeholder={t('portal.allRoles')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('portal.allRoles')}</SelectItem>
              {ROLE_OPTIONS.map(r => (
                <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={status || 'all'} onValueChange={v => updateFilters({ status: v === 'all' ? '' : v })}>
            <SelectTrigger className="w-36">
              <SelectValue placeholder={t('portal.allStatuses')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('portal.allStatuses')}</SelectItem>
              <SelectItem value="active">{t('portal.activeLabel')}</SelectItem>
              <SelectItem value="inactive">{t('customers.inactive')}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        <div className="px-4 lg:px-6">
          <div className="rounded-lg border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableHead label={t('portal.userColumn')} field="name" ordering={ordering} onSort={toggleSort} />
                  <TableHead>{t('portal.role')}</TableHead>
                  <TableHead>{t('common.status')}</TableHead>
                  <SortableHead label={t('portal.joined')} field="created_at" ordering={ordering} onSort={toggleSort} />
                  <TableHead className="text-right">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {usersStatus === 'pending' ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell><div className="flex items-center gap-3"><Skeleton className="h-8 w-8 rounded-full" /><div className="space-y-1"><Skeleton className="h-3 w-32" /><Skeleton className="h-3 w-24" /></div></div></TableCell>
                      <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                      <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                      <TableCell />
                    </TableRow>
                  ))
                ) : !users || users.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-10">
                      {t('portal.noUsers')}
                    </TableCell>
                  </TableRow>
                ) : (
                  users.map(user => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="h-8 w-8 shrink-0">
                            <AvatarFallback className="text-xs bg-gradient-to-br from-emerald-400 to-cyan-500 text-white">
                              {getInitials(user.name, user.email)}
                            </AvatarFallback>
                          </Avatar>
                          <div className="min-w-0">
                            <div className="font-medium text-sm truncate">{user.name || t('portal.noName')}</div>
                            <div className="text-xs text-muted-foreground truncate">{user.email}</div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={roleBadgeVariant(user.role)}>
                          {USER_ROLE_LABELS[user.role] ?? user.role}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={user.is_active ? 'default' : 'secondary'}
                          className={user.is_active ? 'bg-emerald-500 hover:bg-emerald-500' : ''}
                        >
                          {user.is_active ? t('portal.activeLabel') : t('customers.inactive')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                        {new Date(user.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" aria-label="Actions">
                              <MoreHorizontalIcon className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => setUserToEdit(user)}>
                              {t('common.edit')}
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-destructive"
                              onClick={() => setUserToDelete(user)}
                            >
                              {t('common.delete')}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>

      {/* Create User Dialog */}
      <Dialog open={showCreate} onOpenChange={open => { setShowCreate(open); if (!open) createForm.reset() }}>
        <DialogContent className="max-w-[95vw] sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('portal.addNewUser')}</DialogTitle>
          </DialogHeader>
          <Form {...createForm}>
            <form onSubmit={createForm.handleSubmit(data => createMutation.mutate(data))} className="space-y-4">
              <FormField control={createForm.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('portal.fullName')}</FormLabel>
                  <FormControl><Input placeholder="Jane Smith" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={createForm.control} name="email" render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('common.email')}</FormLabel>
                  <FormControl><Input type="email" placeholder="jane@example.com" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={createForm.control} name="password" render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('portal.password')}</FormLabel>
                  <FormControl><Input type="password" placeholder={t('portal.minPassword')} {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={createForm.control} name="role" render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('portal.role')}</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder={t('portal.selectRole')} />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {ROLE_OPTIONS.map(r => (
                        <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={createForm.control} name="is_active" render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <FormLabel className="text-sm font-medium">{t('portal.activeLabel')}</FormLabel>
                    <p className="text-xs text-muted-foreground">{t('portal.canLoginNow')}</p>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )} />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>{t('common.cancel')}</Button>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? t('portal.creating') : t('portal.createUser')}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Edit User Dialog */}
      <Dialog open={!!userToEdit} onOpenChange={open => !open && setUserToEdit(null)}>
        <DialogContent className="max-w-[95vw] sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('portal.editUser')}</DialogTitle>
          </DialogHeader>
          <Form {...editForm}>
            <form onSubmit={editForm.handleSubmit(data => userToEdit && editMutation.mutate({ id: userToEdit.id, data }))} className="space-y-4">
              <FormField control={editForm.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('portal.fullName')}</FormLabel>
                  <FormControl><Input placeholder="Jane Smith" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={editForm.control} name="email" render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('common.email')}</FormLabel>
                  <FormControl><Input type="email" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={editForm.control} name="role" render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('portal.role')}</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {ROLE_OPTIONS.map(r => (
                        <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={editForm.control} name="is_active" render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <FormLabel className="text-sm font-medium">{t('portal.activeLabel')}</FormLabel>
                    <p className="text-xs text-muted-foreground">{t('portal.allowLogin')}</p>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )} />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setUserToEdit(null)}>{t('common.cancel')}</Button>
                <Button type="submit" disabled={editMutation.isPending}>
                  {editMutation.isPending ? t('portal.saving') : t('portal.saveChanges')}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!userToDelete} onOpenChange={open => !open && setUserToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('portal.deleteUser')}</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{userToDelete?.name || userToDelete?.email}</strong> — {t('portal.deleteUserDesc')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => userToDelete && deleteMutation.mutate(userToDelete.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? t('portal.deleting') : t('common.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
