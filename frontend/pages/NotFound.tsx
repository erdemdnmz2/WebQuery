import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeftIcon, CompassIcon } from '@phosphor-icons/react';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';

const NotFound: React.FC = () => {
  const navigate = useNavigate();
  return (
    <EmptyState
      className="my-auto"
      icon={<CompassIcon size={18} />}
      title="Page not found"
      description="The link may have changed or the record may have been deleted. Continue from your workspace list."
      action={
        <Button variant="primary" icon={<ArrowLeftIcon size={14} />} onClick={() => navigate('/')}>
          Back to workspaces
        </Button>
      }
    />
  );
};

export default NotFound;
