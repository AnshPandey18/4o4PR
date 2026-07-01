import React from 'react';

export default function Button({
  children,
  variant = 'primary',
  onClick,
  className = '',
  disabled = false,
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`btn-base btn-${variant} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
