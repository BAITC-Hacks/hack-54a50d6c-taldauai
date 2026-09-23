import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[10px] text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-40',
  {
    variants: {
      variant: {
        default: 'bg-[#171717] text-white hover:bg-[#333]',
        secondary: 'bg-[#f0f0f0] text-[#333] hover:bg-[#e9e9e9]',
        outline: 'border border-[#ddd] bg-white text-[#333] hover:bg-[#f6f6f6]',
        ghost: 'text-[#666] hover:bg-[#efefef] hover:text-[#171717]',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
      },
      size: { default: 'min-h-[38px] px-[13px] py-2', sm: 'min-h-8 rounded-[9px] px-[9px] py-[5px] text-xs', lg: 'min-h-11 px-[18px] py-[11px] text-sm', icon: 'h-9 w-9 rounded-[9px]' },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, ...props }, ref) => (
  <button ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />
))
Button.displayName = 'Button'

export { buttonVariants }
