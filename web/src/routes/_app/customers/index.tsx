import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useLanguage } from '@/contexts/language-context'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { PlusIcon, PencilIcon, TrashIcon } from 'lucide-react'
import { fetchCustomers, deleteCustomer, type Customer } from '@/lib/api'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { CustomerDialog } from '@/components/customer-dialog'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

export const Route = createFileRoute('/_app/customers/')({
  component: CustomersPage,
})

function CustomersPage() {
  const { t } = useLanguage()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [customerToDelete, setCustomerToDelete] = useState<Customer | null>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const { data: customers = [], isLoading } = useQuery({
    queryKey: ['customers'],
    queryFn: () => fetchCustomers(),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteCustomer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      toast.success('Customer deleted successfully')
      setDeleteDialogOpen(false)
      setCustomerToDelete(null)
    },
    onError: () => {
      toast.error('Failed to delete customer')
    },
  })

  const handleAddCustomer = () => {
    setEditingCustomer(null)
    setDialogOpen(true)
  }

  const handleEditCustomer = (customer: Customer, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingCustomer(customer)
    setDialogOpen(true)
  }

  const handleCloseDialog = () => {
    setDialogOpen(false)
    setEditingCustomer(null)
  }

  const handleDeleteClick = (customer: Customer, e: React.MouseEvent) => {
    e.stopPropagation()
    setCustomerToDelete(customer)
    setDeleteDialogOpen(true)
  }

  const handleConfirmDelete = () => {
    if (customerToDelete) {
      deleteMutation.mutate(customerToDelete.id)
    }
  }

  const handleRowClick = (customer: Customer) => {
    navigate({ to: '/customers/$customerId', params: { customerId: String(customer.id) } })
  }

  const getStatusColor = (status: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
    const colorMap: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      active: 'default',
      inactive: 'secondary',
    }
    return colorMap[status] || 'default'
  }

  return (
    <div className="flex flex-1 flex-col min-w-0">
      <div className="flex flex-1 flex-col gap-2 min-w-0">
        <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
          {/* Header */}
          <div className="px-4 lg:px-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h1 className="text-xl sm:text-2xl font-bold">{t('customers.title')}</h1>
                <p className="text-sm text-muted-foreground">
                  {t('customers.subtitle')}
                </p>
              </div>
              <Button onClick={handleAddCustomer} className="bg-primary text-primary-foreground hover:bg-primary/90">
                <PlusIcon className="h-4 w-4" />
                <span className="hidden sm:inline">{t('customers.addCustomer')}</span>
                <span className="sm:hidden">{t('common.add')}</span>
              </Button>
            </div>
          </div>

          {/* Customers Table */}
          <div className="px-4 lg:px-6 min-w-0">
            <div className="rounded-md border overflow-x-auto min-w-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="min-w-[120px]">{t('leads.contactPerson')}</TableHead>
                    <TableHead className="min-w-[140px]">{t('common.email')}</TableHead>
                    <TableHead className="min-w-[110px]">{t('common.phone')}</TableHead>
                    <TableHead className="min-w-[80px]">{t('common.status')}</TableHead>
                    <TableHead className="min-w-[80px]">{t('leads.source')}</TableHead>
                    <TableHead className="min-w-[80px]">{t('customers.channels')}</TableHead>
                    <TableHead className="text-right min-w-[80px]">{t('common.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                        {t('common.loading')}
                      </TableCell>
                    </TableRow>
                  ) : customers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                        {t('customers.noCustomers')}
                      </TableCell>
                    </TableRow>
                  ) : (
                    customers.map((customer) => (
                      <TableRow
                        key={customer.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => handleRowClick(customer)}
                      >
                        <TableCell className="font-medium truncate max-w-[150px]">{customer.contact_person}</TableCell>
                        <TableCell>
                          <div className="min-w-0">
                            <div className="truncate">{customer.contact_person}</div>
                            <div className="text-xs text-muted-foreground truncate">{customer.email}</div>
                          </div>
                        </TableCell>
                        <TableCell>{customer.phone || '-'}</TableCell>
                        <TableCell>
                          <Badge variant={getStatusColor(customer.customer_status)}>
                            {customer.customer_status_display}
                          </Badge>
                        </TableCell>
                        <TableCell>{customer.source || '-'}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            {customer.has_telegram ? (
                              <span title="Telegram" className="text-lg">💬</span>
                            ) : null}
                            {customer.has_instagram ? (
                              <span title="Instagram" className="text-lg">📸</span>
                            ) : null}
                            {customer.has_whatsapp ? (
                              <span title="WhatsApp" className="text-lg">📱</span>
                            ) : null}
                            {!customer.has_telegram && !customer.has_instagram && !customer.has_whatsapp ? (
                              <span className="text-muted-foreground text-sm">-</span>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={(e) => handleEditCustomer(customer, e)}
                              aria-label="Edit"
                            >
                              <PencilIcon className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={(e) => handleDeleteClick(customer, e)}
                              aria-label="Delete"
                            >
                              <TrashIcon className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </div>
        </div>
      </div>

      <CustomerDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        customer={editingCustomer}
        onClose={handleCloseDialog}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Customer</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {customerToDelete?.contact_person}? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
